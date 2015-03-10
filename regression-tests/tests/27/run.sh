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

lnst-ctl -d run recipe5.xml | tee test.log
rv5=${PIPESTATUS[0]}
log5=`cat test.log`

lnst-ctl -d run recipe6.xml | tee test.log
rv6=${PIPESTATUS[0]}
log6=`cat test.log`

lnst-ctl -d run recipe7.xml | tee test.log
rv7=${PIPESTATUS[0]}
log7=`cat test.log`

print_separator
assert_status "pass" "$rv1"
assert_status "pass" "$rv2"
assert_status "fail" "$rv3"
assert_log "INFO" "RPC connection to machine testmachine1 timed out" "$log3"
assert_status "pass" "$rv4"
assert_status "pass" "$rv5"
assert_status "pass" "$rv6"
assert_status "fail" "$rv7"
assert_log "INFO" "RPC connection to machine testmachine1 timed out" "$log7"

rm -f test.log

end_test
