#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run prefix-check.xml | tee test10.log
rv=${PIPESTATUS[0]}

log=`cat test10.log`

rm -f test10.log

print_separator

assert_status "pass" "$rv"

assert_log "DEBUG" "echo 24" "$log"
assert_log "DEBUG" "echo 192.168.200.4" "$log"
assert_log "DEBUG" "echo 16" "$log"
assert_log "DEBUG" "echo 192.168.202.4" "$log"

lnst-ctl -d run prefix-check-taskapi.xml | tee test10-api.log
rv=${PIPESTATUS[0]}

log=`cat test10-api.log`

rm -f test10-api.log

print_separator

assert_status "pass" "$rv"

assert_log "DEBUG" "echo 24" "$log"
assert_log "DEBUG" "echo 192.168.200.4" "$log"
assert_log "DEBUG" "echo 16" "$log"
assert_log "DEBUG" "echo 192.168.202.4" "$log"

end_test
