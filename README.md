Routechoices.com
==================

Live GPS Tracking Solution for orienteering events.

Run in docker
-------------

1. `./dc build`
2. `./dc up -d`
3. Dump database from production (see below).
4. Copy media files from production (see below)
5. `./dc restoredb postgres.bak`
6. `./dc restart web`


Take dumps from production
--------------------------

Take a note of the production database password:

Copy database from production:

    $ ssh wf pg_dump -Fc -h localhost -p 5432 -U rphl routechoices > postgres.bak

Copy media from production:

    $ rsync -avz wf:/home/rphl/webapps/routechoices/media media/
