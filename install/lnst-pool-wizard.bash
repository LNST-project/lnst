#!/bin/bash

# Bash completion script for lnst-pool-wizard command
# Author: Jiri Prochazka <jprochaz@redhat.com>

_lnst_pool_wizard()
{
    local SHORT_OPTS="-h -i -n -v"
    local LONG_OPTS="--help --interactive --noninteractive --virtual"
    local REQUIRE_ARG="-p --pool_dir"

    local cur=${COMP_WORDS[COMP_CWORD]}
    local prev=${COMP_WORDS[COMP_CWORD-1]}

    case "$prev" in
        -p|--pool_dir)
            _filedir
            return 0
            ;;
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

complete -o nospace -F _lnst_pool_wizard lnst-pool-wizard
