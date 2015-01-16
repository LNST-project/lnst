#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe.xml | tee test.log
rv=${PIPESTATUS[0]}

log=`cat test.log`

rm -f test.log

print_separator

assert_status "error" "$rv"
assert_log "ERROR" "Parser error:" "$log"

end_test
