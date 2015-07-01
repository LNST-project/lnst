#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d config_only recipe1.xml | tee test.log
rv1=${PIPESTATUS[0]}

lnst-ctl -d run recipe2.xml | tee test.log
rv2=${PIPESTATUS[0]}


print_separator
assert_status "pass" "$rv1"
assert_status "pass" "$rv2"

rm -f test.log

end_test
