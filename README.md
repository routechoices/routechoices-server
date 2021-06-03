[![rphlo](https://circleci.com/gh/rphlo/routechoices-server.svg?style=shield)](https://circleci.com/gh/rphlo/routechoices-server)

Routechoices.com
==================

Live GPS Tracking Solution for orienteering events.

Run in docker for local development
-----------------------------------

1. `./dc build`
2. `./dc up -d`
3. `./da migrate`
4. `./dc restart web`


Take dumps from production
--------------------------

Copy media from production:

    $ rsync -avz <host>:<>/media ./

Copy database from production:
Take a note of the production database password

    $ ssh <host> pg_dump -Fc -h localhost -p 5432 -U <db_user> <db_name> > postgres.bak
    <Enter Password>
    $ ./dc restoredb postgres.bak
    $ ./dc restart web
