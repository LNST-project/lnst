#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe_fail.xml | tee test.log
rv1=${PIPESTATUS[0]}
log1=`cat test.log`

lnst-ctl -d run recipe_pass.xml | tee test.log
rv2=${PIPESTATUS[0]}
log2=`cat test.log`

print_separator
assert_status "fail" "$rv1"
assert_log "INFO" "RPC connection to machine \w* timed out" "$log1"
assert_status "pass" "$rv2"

rm -f test.log

end_test
