#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d config_only recipe1.xml | tee test.log
rv1=${PIPESTATUS[0]}
log1=`cat test.log`

lnst-ctl -d config_only recipe2.xml | tee test.log
rv2=${PIPESTATUS[0]}
log2=`cat test.log`

lnst-ctl -d deconfigure

print_separator
assert_status "error" "$rv1"
assert_log "ERROR" "CommandException: Slave testmachine1" "$log1"
assert_status "pass" "$rv2"

rm -f test.log

end_test
