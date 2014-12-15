#!/bin/bash

. ../lib.sh

# initialize the test
init_test

# In this case, we want to catch the log for asserts.
log="`lnst-ctl`"
rv=$?

# But we also want the log to be shown in test results.
echo "$log"

# To keep the lnst-ctl log separated from the asserts
print_separator

assert_log "ERROR" "No action specified" "$log"

# Check the return value
assert_status "error" $rv

# finish the test
end_test
