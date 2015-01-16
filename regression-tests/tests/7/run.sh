#!/bin/bash

. ../lib.sh

init_test

log=`lnst-ctl -d run recipe.xml`
rv=$?

echo "$log"
print_separator

assert_log ".*" "1_\([a-fA-F0-9]\{2\}:\?\)\{6\}_" "$log"
assert_log ".*" "2_52:54:00:12:34:56_" "$log"
assert_log ".*" "3_\(\([a-fA-F0-9]\{2\}:\?\)\{6\}\)_\1_" "$log"

assert_status "pass" "$rv"

end_test
