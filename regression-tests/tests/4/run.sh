#!/bin/bash

. ../lib.sh

init_test

log="`lnst-ctl -d run recipe.xml`"
rv=$?

echo "$log"
print_separator

assert_log "DEBUG" "echo 1_one_two" "$log"
assert_log "DEBUG" "echo 2_eno_owt" "$log"
assert_log "DEBUG" "echo 3_one_two" "$log"

assert_status "pass" "$rv"

end_test
