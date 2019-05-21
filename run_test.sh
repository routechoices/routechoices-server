#! /bin/bash
./dc up -d
./da reset_db_for_tests
./dc restart web 
docker run -it -v $PWD:/e2e -w /e2e --network="host" cypress/included:3.2.0
