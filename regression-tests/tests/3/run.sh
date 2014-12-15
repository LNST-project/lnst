#!/bin/bash

. ../lib.sh

init_test

lnst-ctl -d run recipe.xml
rv=$?

assert_status "error" "$rv"

end_test
