#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe1.xml | tee test.log
rv1=${PIPESTATUS[0]}
log1=`cat test.log`

lnst-ctl -d run recipe2.xml | tee test.log
rv2=${PIPESTATUS[0]}
log2=`cat test.log`

lnst-ctl -d run recipe3.xml | tee test.log
rv3=${PIPESTATUS[0]}
log3=`cat test.log`

print_separator
assert_status "pass" "$rv1"
assert_status "pass" "$rv2"
assert_status "pass" "$rv3"
assert_log "ERROR" "Command execution failed (exited with -2)" "$log3"

rm -f test.log

end_test
