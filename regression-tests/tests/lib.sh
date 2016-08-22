#!/bin/bash

function init_test
{
    # test status 0 means everything went fine, 1 means there were
    # one or more problems.
    test_status=0
}

function end_test
{
    exit "$test_status"
}

function assert_log
{
    local level="$1"
    local message_regexp="$2"
    local log="$3"

    if [ -z "`echo "$log" | grep "$level" | grep "$message_regexp"`" ]; then
        echo "assert_log FAILED ($level, $message_regexp)"
        test_status=1
    else
        echo "assert_log PASSED ($level, $message_regexp)"
    fi
}

function assert_status
{
    local expect="$1"
    local retval="$2"

    case $expect in
        "pass")
            local value=0 ;;
        "fail")
            local value=1 ;;
        "error")
            local value=2 ;;
        *)
            echo "Unknown exit status '$expect'!"
            exit 128
            ;;
    esac

    if [ $value -ne $retval ]; then
        test_status=1
        echo "assert_status FAILED (expected: $value, real: $retval)"
    else
        echo "assert_status PASSED (expected: $value, real: $retval)"
    fi
}

function print_separator
{
    echo "--------------------------------------------------------------------------------"
}
