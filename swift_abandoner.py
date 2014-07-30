#!/usr/bin/env python

import argparse
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

DB_DIRECTORY = "/tmp/swift_abandon_db_data/"
LOG_FILE = DB_DIRECTORY + "/swift_abandon.log"
DB_FILENAME = "abandon_data"

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


def send_email(send_from, send_to, subject, text, files=[], server="localhost"):
    if not isinstance(send_to, list):
        send_to = [send_to]

    if not isinstance(files, list):
        files = [files]

    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = COMMASPACE.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(text))

    for f in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(f, "rb").read())
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(f))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.close()


class AbandonException(Exception):
    pass


class Abandon():
    def __init__(self, config):
        self.config = config
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

    def _get_existing_changes(self):
        results = []
        cur = self.conn.cursor(mdb.cursors.DictCursor)
        cur.execute("SELECT * from changes WHERE deleted = 0")
        rows = cur.fetchall()
        for row in rows:
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

    def _send_notification(self, change):
        sent = 0
        try:
            subject = self.config[EMAIL_SUBJECT] % change
            msg = self.config[EMAIL_TEMPLATE] % change
            to = "matt+abandon@oliver.net.au"
            send_email(self.config[EMAIL_FROM], to, subject, msg)
            sent = 1
        except:
            sent = 0

        # Insert the notificaiton record
        cur = self.conn.cursor()
        cur.execute("INSERT INTO notifications (email, sent, date_sent)"
                    " VALUES (%s, %s, NOW())", (change[CH_EMAIL], str(sent)))
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
            cur.execute("UPDATE changes SET deleted = 1, deleted_at = NOW() "
                        "WHERE deleted = 0 AND `number` = %s", change)
            self.conn.commit()

    def _add_change(self, change):
        cur = self.conn.cursor()
        change.update(change['owner'])
        cur.execute(SQL_INSERT_CHANGE, (change[CH_NUMBER], change[CH_MERGEABLE],
                    change[CH_BRANCH], change[CH_SUBJECT],
                    change[CH_CREATED].split('.')[0],
                    change[CH_UPDATED].split('.')[0], change.get(CH_NAME, ''),
                    change.get(CH_USERNAME, ''), change[CH_EMAIL]))
        self.conn.commit()

    def _get_existing_change_numbers(self):
        cur = self.conn.cursor()
        cur.execute("SELECT number FROM changes "
                    "WHERE deleted = 0")
        res = cur.fetchall()
        return [row[0] for row in res]

    def run_once(self):
        current_changes = self._get_current_data()
        existing_changes = self._get_existing_change_numbers()

        for change in current_changes:
            if change[CH_NUMBER] in existing_changes:
                existing_changes.remove(change[CH_NUMBER])
            else:
                # This is a new change so add it
                self._add_change(change)

        # Any change numbers left in existing_changes can be deleted
        self._delete_changes(existing_changes)

        # check and (re)send notifications
        self._process_notifications()

    def send_email(self):
        pass

    def process_change(self, change):
        pass

    def _setup_logger(self):
        log_file = self.config.get('log-file', '/tmp/abandon.log')
        log_level = self.config.get('log-level', 'DEBUG')
        logging.basicConfig(format='%(asctime)s %(name)-32s '
                            '%(levelname)-8s %(message)s',
                            filename=log_file,
                            level=getattr(logging, log_level))

    def import_data(self):
        """ Data will be in the form of:
        {change: date_found}
        """
        try:
            with open(os.path.join(DB_DIRECTORY, DB_FILENAME)) as json_stream:
                data = json.load(json_stream)
        except:
            self.log.warn("Database file not found, not importing old data")
            data = {}
        return data

    def _get_current_data(self):
        try:
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
                        default=
                        '/home/matt/programming/junk/swift_abandon/config.yaml',
                        help='Path to yaml config file.')
    args = parser.parse_args()
    config = {}
    with open(args.config) as config_stream:
        config = yaml.load(config_stream)
    abandon = Abandon(config)
    abandon.run_once()

if __name__ == "__main__":
    main()
