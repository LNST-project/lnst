#!/bin/bash

. ../lib.sh

init_test

touch test_modules/*

lnst-ctl -c lnst-ctl.conf -d run recipe.xml | tee test.log
rv=${PIPESTATUS[0]}

log=`cat test.log`

print_separator
assert_status "pass" "$rv"

rm -f test.log

end_test
