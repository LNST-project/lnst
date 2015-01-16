#!/bin/bash

. ../lib.sh

init_test

touch test_tools/*
touch test_modules/*

lnst-ctl -c lnst-ctl.conf -d -r run recipe.xml | tee test.log
rv=${PIPESTATUS[0]}

print_separator
assert_status "pass" "$rv"

rm -f test.log

end_test
