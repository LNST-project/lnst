#!/bin/bash

. ../lib.sh

init_test

lnst-ctl run recipe.xml
rv=$?

assert_status "pass" "$rv"

end_test
