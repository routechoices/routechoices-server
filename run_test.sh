#! /bin/bash
set -e
./dc up -d
./da test
./da reset_db_for_tests
./dc restart django 
docker run -it -v $PWD:/e2e -w /e2e --network="host" cypress/included:3.2.0
