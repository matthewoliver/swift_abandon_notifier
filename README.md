Swift Abandon Notifier (AKA swift abandon bot)
===============================================

The swift abandon notifier is a simple script which queries the review.openstack.org gerrit server for swift changes that are possibly abandoned.

The criteria is:
  - Change has a '-1';
  - Not WIP; AND
  - Hasn't been updated in >= weeks.

It then processes the results and stores them in a MySQL database. If it hasn't notified the owner and email is sent, this notification is then also stored, allowing statisical analysis.

The script then will generate a HTML page with a list of changes that are considered abandoned, this is done by doing a query on the database to see which changes still exist and its been X days since a successful notification was sent. Where X is configurable in the config file.
