Swift Abandon Notifier (AKA swift abandon bot)
===============================================

The swift abandon notifier is a simple script which queries the review.openstack.org gerrit server for swift changes that are possibly abandoned.

The criteria is:
  - Change has a '-1';
  - Not WIP; AND
  - Hasn't been updated in >= 4 weeks.

It stores these results in a MySQL database (see schema.sql). If a changes' owner hasn't been notified then an email is sent. If the notification is sent successfully or not, an entry is made in the notifications table to allow for future statistical analysis. Further, if a change now doesn't exist in the query from gerrit (due to it actually being abandoned or by someone updating the change) then a delete flag is marked in the database, again for future statistical analysis.

The script then generates an HTML report of changes it deems are abandoned. But only creates the report if:
  - The report HTML doesn't exist.
  - If there are items in the report.

The script deems that a change has been abandoned if the change still hasn't been updated and X (default 14) days have passed since the notification warning has been sent. Where X is configured in config.yaml.

See config.yaml for all the configuration options including the email template sent.

NOTE: At the moment, the HTML report is generated, so a swift core can see the list of abandoned changes, know that the owner has had ample to do something and can abandon it. It would be possible to get this script to auto-abandon changes, but that requires it to log in gerrit as a core, which hasn't been implemented yet.
