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

lnst-ctl -d run recipe4.xml | tee test.log
rv4=${PIPESTATUS[0]}
log4=`cat test.log`

print_separator
assert_status "pass" "$rv1"
assert_status "pass" "$rv2"
assert_status "pass" "$rv3"
assert_status "pass" "$rv4"
assert_log "INFO" "stdout:.*test" "$log1"
assert_log "INFO" "stdout:.*test" "$log2"
assert_log "INFO" "stdout:.*test" "$log4"

rm -f test.log

end_test
