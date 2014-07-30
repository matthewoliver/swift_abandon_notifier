Swift Abandon Notifier (AKA swift abandon bot)
===============================================

The swift abandon notifier is a simple script which queries the review.openstack.org gerrit server for swift changes that are possibly abandoned.

The criteria is:
  - Change has a '-1';
  - Not WIP; AND
  - Hasn't been updated in >= weeks.

It then processes the results and stores them in a MySQL database. If it hasn't notified the owner and email is sent, this notification is then also stored, allowing statisical analysis.

There will be another part of this script (probably a simple php file) which will connect to the database and list patches it has determined are ready to be abanonded. It depermines this by the change still being found in the gerrit query 2 weeks after the notification has been sent.
