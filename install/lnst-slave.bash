#!/bin/bash

# Bash completion script for lnst-slave command
# Author: Radek Pazdera <rpazdera@redhat.com>

_lnst_slave()
{
    local SHORT_OPTS="-d -e -h -i -m -p"
    local LONG_OPTS="--debug --daemonize --help --pidfile --no-colours --port"
    local REQUIRE_ARG="-i --pidfile -p --port"

    local cur=${COMP_WORDS[COMP_CWORD]}
    local prev=${COMP_WORDS[COMP_CWORD-1]}

    # Look for option arguments first
    case "$prev" in
        -i|--pidfile)
            _filedir
            return 0
            ;;
        -p|--port) return 0 ;;
    esac

    # Complete long and shor options
    if [[ "$cur" == --* ]]; then
        COMPREPLY=( $(compgen -W "$LONG_OPTS" -- $cur) )
        [ ${#COMPREPLY[@]} = 1 ] && COMPREPLY=$(printf %q%s "$COMPREPLY" " ")
        return 0
    elif [[ "$cur" == -* ]]; then
        COMPREPLY=( $(compgen -W "$SHORT_OPTS" -- $cur) )
        [ ${#COMPREPLY[@]} = 1 ] && COMPREPLY=$(printf %q%s "$COMPREPLY" " ")
        return 0
    fi

    return 0
}

complete -o nospace -F _lnst_slave lnst-slave
