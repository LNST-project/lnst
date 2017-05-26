# Bash completion script for lnst-ctl command
# Author: Radek Pazdera <rpazdera@redhat.com>

_list_has_item()
{
    for entry in $1; do
        [ "$entry" == "$2" ] && return 0
    done

    return 1
}

_lnst_ctl()
{
    local SHORT_OPTS="-a -A -c -C -d -h -m -o -p -r -u -x -v"
    local LONG_OPTS="--define-alias --override-alias \
                     --config --config-override \
                     --debug --help --no-colours --disable-pool-checks \
                     --packet-capture --pools --reduce-sync \
                     --result --multi-match --verbose"
    local REQUIRE_ARG="-a --define-alias \
                       -A --override-alias \
                       -c --config \
                       -C --config-override \
                       -x --result \
                       --pools"
    local ACTIONS="config_only match_setup run list_pools deconfigure"

    local cur=${COMP_WORDS[COMP_CWORD]}
    local prev=${COMP_WORDS[COMP_CWORD-1]}

    # Look for option arguments first
    case "$prev" in
        -a|--define-alias) return 0 ;;
        -A|--override-alias) return 0 ;;
        -c|--config|-C|--config-override)
            _filedir
            return 0
            ;;
        -x|--result)
            _filedir
            return 0
            ;;
        --pools)
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

    # Check if the action positional argument has
    # already been specified somewhere
    for (( n=1; n < $COMP_CWORD; n++ )); do
        local word=${COMP_WORDS[n]}
        local prev_word=${COMP_WORDS[n-1]}

        # Is it an option?
        if [[ "$word" == --* ]] || [[ "$word" == -* ]]; then
            continue
        else
            # Is the previous word an option that requires and argument?
            _list_has_item "$REQUIRE_ARG" "$prev_word"
            if [ $? -eq 0 ]; then
                continue
            else
                # Is the positional argument an action?
                _list_has_item "$ACTIONS" "$word"
                if [ $? -eq 0 ]; then
                    # Action positional argument was found.
                    # Therefore, we will suggest files.
                    _filedir
                    return 0
                fi
            fi
        fi
    done

    # No action defined yet, we will suggest actions.
    COMPREPLY=( $(compgen -W "$ACTIONS" -- $cur) )
    [ ${#COMPREPLY[@]} = 1 ] && COMPREPLY=$(printf %q%s "$COMPREPLY" " ")

    return 0
}

complete -o nospace -F _lnst_ctl lnst-ctl
