#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -c lnst-ctl.conf -d run recipe.xml | tee test.log
rv=${PIPESTATUS[0]}

log=`cat test.log`

print_separator
assert_status "error" "$rv"
assert_log "error" "You have the same machine listed twice in your pool" "$log"

rm -f test.log

end_test
