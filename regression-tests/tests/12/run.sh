#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run xinclude-check.xml
rv=$?

assert_status "pass" "$rv"

end_test
