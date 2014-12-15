#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run taskapi-alias-check.xml
rv=$?

assert_status "pass" "$rv"

lnst-ctl -d -A alias1="value2" run taskapi-alias-check.xml
rv=$?

assert_status "fail" "$rv"

lnst-ctl -d run taskapi-alias-namespace-check.xml
rv=$?

assert_status "error" "$rv"

end_test
