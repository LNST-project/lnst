#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe1.xml
rv=$?

assert_status "pass" "$rv"

lnst-ctl -d run recipe2.xml
rv=$?

assert_status "pass" "$rv"

end_test
