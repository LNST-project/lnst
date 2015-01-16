#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe.xml
rv=$?

print_separator

assert_status "pass" "$rv"

end_test
