#!/usr/bin/env python

import argparse
import datetime
import jinja2
import json
import logging
import MySQLdb as mdb
import os
import requests
import smtplib
import yaml

from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

DEBUG = True

SQL_INSERT_CHANGE = """INSERT INTO changes (
                    number, mergeable, branch, subject, created, updated,
                    owner, username, email, deleted) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)"""

# Constants
CH_NUMBER = "_number"
CH_MERGEABLE = DB_MERGEABLE = "mergeable"
CH_BRANCH = DB_BRANCH = "branch"
CH_SUBJECT = DB_SUBJECT = "subject"
CH_CREATED = DB_CREATED = "created"
CH_UPDATED = DB_UPDATED = "updated"
CH_NAME = "name"
CH_USERNAME = DB_USERNAME = "username"
CH_EMAIL = DB_EMAIL = "email"

DB_ID = 'id'
DB_NUMBER = "number"
DB_OWNER = "owner"
DB_DELETED = "deleted"

EMAIL_TEMPLATE = "email_template"
EMAIL_SUBJECT = "email_subject"
EMAIL_FROM = "email_from"
EMAIL_CC = "email_cc"
EMAIL_BCC = "email_bcc"

CONF_TEMPLATE_DIR = "template_direcotry"
CONF_TEMPLATE = "template"
CONF_HTML_FILE = "html_filename"
CONF_ABANDONED_DAYS = "abandoned_days"


def send_email(send_from, send_to, subject, text, files=[],
               server="localhost", cc=[], bcc=[]):
    if not isinstance(send_to, list):
        send_to = [send_to]

    if files:
        if not isinstance(files, list):
            files = [files]

    if cc:
        if not isinstance(cc, list):
            cc = [cc]

    if bcc:
        if not isinstance(bcc, list):
            bcc = [bcc]

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)

    if cc:
        msg['Cc'] = COMMASPACE.join(cc)
        send_to += cc

    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    if bcc:
        send_to += bcc

    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(f, "rb").read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' %
                        os.path.basename(f))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


class AbandonException(Exception):
    pass


class Abandon():
    def __init__(self, config, whitelist=None):
        self.config = config
        self.whitelist = whitelist
        self.log = logging.getLogger("Swfit.change.abandoner")
        self._setup_logger()
        try:
            self.conn = mdb.connect(host=config['host'],
                                    user=config['user'],
                                    passwd=config['password'],
                                    db=config['database'],
                                    port=config['port'])
        except Exception as ex:
            self.log.error("Failed to connect to mysql")
            raise ex

    def _generate_html(self, changes):
        html_file = self.config.get(CONF_HTML_FILE,
                                    '/var/www/abandoned_changes.html')
        html_exists = os.path.exists(html_file)
        if html_exists:
            self.log.info("Regenerating abandon HMTL: %s", html_file)
        else:
            self.log.info("Generating abandon HMTL: %s", html_file)

        searchpath = self.config.get(CONF_TEMPLATE_DIR,
                                     "/etc/abandoner/templates")
        templateLoader = jinja2.FileSystemLoader(searchpath=searchpath)
        templateEnv = jinja2.Environment(loader=templateLoader)
        template_file = self.config.get(CONF_TEMPLATE,
                                        "abandoned_changes.jinja")
        template = templateEnv.get_template(template_file)
        days = self.config.get(CONF_ABANDONED_DAYS, 14)
        template_vars = {"changes": changes, "days": days}
        output_text = template.render(template_vars)

        with open(html_file, "w") as html_stream:
            html_stream.write(output_text)

        if html_exists:
            self.log.info("Abandon HTML regeneration complete.")
        else:
            self.log.info("Abandon HTML generation complete.")

    def _process_abandoned_changes(self):
        # get the date of CONF_ABANDONED_DAY ago.
        abandon_days = self.config.get(CONF_ABANDONED_DAYS, 14)
        date_delta = datetime.timedelta(days=abandon_days)
        abandon_date = datetime.datetime.now() - date_delta

        sql = "SELECT * from changes c, notifications n "
        sql += "WHERE n.change_id = c.id AND c.deleted = 0 AND "
        sql += "n.sent = 1 AND date_sent <= %s"
        changes = self._get_changes(sql, (abandon_date,))

        html_file = self.config.get(CONF_HTML_FILE,
                                    '/var/www/abandoned_changes.html')
        if changes or not os.path.exists(html_file):
            self._generate_html(changes)

    def _is_whitelisted(self, change):
        if self.whitelist:
            for item in self.whitelist:
                if item:
                    k, v = item.popitem()
                    if change[k] == v:
                        True
        return False

    def _get_changes(self, sql, variables=()):
        results = []
        cur = self.conn.cursor(mdb.cursors.DictCursor)
        if variables:
            cur.execute(sql, variables)
        else:
            cur.execute(sql)
        rows = cur.fetchall()
        for row in rows:
            if self._is_whitelisted(row):
                continue
            results.append({
                CH_NUMBER: row[DB_NUMBER],
                CH_MERGEABLE: row[DB_MERGEABLE],
                CH_BRANCH: row[DB_BRANCH],
                CH_SUBJECT: row[DB_SUBJECT],
                CH_CREATED: row[DB_CREATED],
                CH_UPDATED: row[DB_UPDATED],
                CH_NAME: row[DB_OWNER],
                CH_USERNAME: row[DB_USERNAME],
                CH_EMAIL: row[DB_EMAIL],
                DB_ID: row[DB_ID]})
        return results

    def _get_existing_changes(self):
        sql = "SELECT * from changes WHERE deleted = 0"
        return self._get_changes(sql)

    def _send_notification(self, change):
        sent = 0
        try:
            subject = self.config[EMAIL_SUBJECT] % change
            msg = self.config[EMAIL_TEMPLATE] % change
            to = change[CH_EMAIL]
            cc = self.config.get(EMAIL_CC, [])
            bcc = self.config.get(EMAIL_BCC, [])
            send_email(self.config[EMAIL_FROM], to, subject,
                       msg, cc=cc, bcc=bcc)
            self.log.info("Sent nofitication for change %(_number)s" % change)
            sent = 1
        except:
            self.log.info("Failed to send nofitication for change %(_number)s"
                          % change)
            sent = 0

        # Insert the notificaiton record
        cur = self.conn.cursor()
        cur.execute("INSERT INTO notifications (email, sent, date_sent, "
                    "change_id) VALUES (%s, %s, NOW(), %s)",
                    (change[CH_EMAIL], str(sent), change[DB_ID]))
        self.conn.commit()

    def _process_notifications(self):
        existing_changes = self._get_existing_changes()
        for change in existing_changes:
            cur = self.conn.cursor(mdb.cursors.DictCursor)
            cur.execute("SELECT count(id) as c FROM notifications n "
                        "WHERE n.id = %s AND sent = 1", (str(change[DB_ID]),))
            row = cur.fetchone()
            if int(row['c']) == 0:
                # A sucessful notification hasn't been sent.
                self._send_notification(change)

    def _delete_changes(self, change_numbers):
        cur = self.conn.cursor()
        for change in change_numbers:
            self.log.info("Deleting change %d" % change)
            cur.execute("UPDATE changes SET deleted = 1, deleted_at = NOW() "
                        "WHERE deleted = 0 AND `number` = %s", (change,))
            self.conn.commit()

    def _add_change(self, change):
        cur = self.conn.cursor()
        change.update(change['owner'])
        if CH_EMAIL not in change:
            # No email address, this seems to happen when the change is
            # raised from the 'OpenStack Proposal Bot'. So I'll use the
            # donotreply email address here as the email will automatically
            # be deleted, but the people BCC'd will still get the notification
            # email.
            change[CH_EMAIL] = self.config[EMAIL_FROM]
        cur.execute(SQL_INSERT_CHANGE, (change[CH_NUMBER], change[CH_MERGEABLE],
                    change[CH_BRANCH], change[CH_SUBJECT],
                    change[CH_CREATED].split('.')[0],
                    change[CH_UPDATED].split('.')[0], change.get(CH_NAME, ''),
                    change.get(CH_USERNAME, ''), change[CH_EMAIL]))
        self.conn.commit()
        self.log.info("Added change %(_number)s" % change)

    def _get_existing_change_numbers(self):
        cur = self.conn.cursor()
        cur.execute("SELECT number FROM changes "
                    "WHERE deleted = 0")
        res = cur.fetchall()
        return [row[0] for row in res]

    def run_once(self):
        self.log.info("Starting run")
        current_changes = self._get_current_data()
        existing_changes = self._get_existing_change_numbers()

        for change in current_changes:
            if change[CH_NUMBER] in existing_changes:
                existing_changes.remove(change[CH_NUMBER])
            else:
                # This is a new change so add it
                if not self._is_whitelisted(change):
                    self._add_change(change)

        # Any change numbers left in existing_changes can be deleted
        self._delete_changes(existing_changes)

        # check and (re)send notifications
        self._process_notifications()

        self._process_abandoned_changes()
        self.log.info("Finished run")

    def _setup_logger(self):
        log_file = self.config.get('log-file',
                                   '/var/log/abandoner/abandon.log')
        log_level = self.config.get('log-level', 'DEBUG')
        logging.basicConfig(format='%(asctime)s %(name)-32s '
                            '%(levelname)-8s %(message)s',
                            filename=log_file,
                            level=getattr(logging, log_level))

    def _get_current_data(self):
        try:
            self.log.info("Querying gerrit")
            session = requests.Session()
            resp = session.get(self.config['gerrit-url'] %
                               self.config['gerrit-query'],
                               headers={'Accept': 'application/json',
                                        'Accept-Encoding': 'gzip'})
            changes = json.loads(resp.text[4:])
            return changes
        except Exception as ex:
            print ex
            self.log.error("Failed to talk to gerrit")
            raise AbandonException("Failed to talk to gerrit")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config',
                        default='/etc/abandoner/config.yaml',
                        help='Path to yaml config file.')
    parser.add_argument('-w', '--whitelist',
                        default='/etc/abandoner/whitelist.yaml',
                        help='Path to yaml whitelist file.')
    args = parser.parse_args()
    config = {}
    with open(args.config) as config_stream:
        config = yaml.load(config_stream)

    whitelist = None
    if os.path.exists(args.whitelist):
        with open(args.whitelist) as whitelist_stream:
            whitelist = yaml.load(whitelist_stream)
    abandon = Abandon(config, whitelist)
    abandon.run_once()

if __name__ == "__main__":
    main()
