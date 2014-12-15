#!/bin/bash

. ../lib.sh

init_test

log="`lnst-ctl -d run recipe.xml`"
rv=$?

echo "$log"
print_separator

assert_log "DEBUG" "echo ip1_192.168.100.10_" "$log"
assert_log "DEBUG" "echo ip2_192.168.100.10_" "$log"
assert_log "DEBUG" "echo hwaddr_\([a-fA-F0-9]\{2\}:\?\)\{6\}_" "$log"
assert_log "DEBUG" "echo devname_[a-zA-Z0-9]\+_" "$log"

assert_status "pass" "$rv"

end_test
