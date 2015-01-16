#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe.xml | tee test.log
rv=${PIPESTATUS[0]}

log=`cat test.log`

rm -f test.log

print_separator

assert_status "error" "$rv"
assert_log "ERROR" "Second parameter of function ip() is invalid" "$log"

end_test
