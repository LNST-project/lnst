#!/usr/bin/bash

function get_hostname
{
    sed -n "s/.*param name=['\"]hostname['\"] value=['\"]\([^'\"]\+\)['\"].*/\1/p" $1
}

function log
{
    if [ -n "$log_dir" ]; then
        echo "$1" | tee -a "$log_dir/log"
    else
        echo "$1"
    fi
}

function logn
{
    if [ -n "$log_dir" ]; then
        echo -n "$1" | tee -a "$log_dir/log"
    else
        echo -n "$1"
    fi
}

function logtest
{
    if [ -n "$log_dir" ]; then
        log_path="$log_dir/$test_dir"
        mkdir -p "$log_path"
        (tee $log_path/stdout.log) 3>&1 1>&2 2>&3 | tee $log_path/stderr.log
    else
        cat
    fi
}

function print_separator
{
    log "--------------------------------------------------------------------------------"
}

function usage
{
    echo "Usage: $0 [-c] [-r revision] [-l logdir] [-t list_of_tests] [-u url] [-n]"
    echo "    -r revision       Test a specific git branch/rev/tag"
    echo "                      Note: ignored when -s is used"
    echo "    -l logdir         Save test results to a directory"
    echo "    -t list_of_tests  Run only these tests"
    echo "                      Example: -t 0,1,2 will run tests 0, 1, and 2"
    echo "    -n                Disable use of NetworkManager on slavemachines"
    echo "                      Note: enabled by default"
    echo "    -u url            URL pointing to LNST repository that should be used"
    echo "                      Note: git clone and checkout by default"
    echo "    -s                use rsync instead of git"
    echo "    -c                use user configuration"
    exit 0
}

# ---

#default repository url
url="../"
use_git=true
export use_user_conf="false"

while getopts "chlr:t:g:ns" OPTION
do
    case $OPTION in
        c)  use_user_conf="true" ;;
        h)  usage ;;
        l)  log_dir_name="results-`date "+%Y-%m-%d-%I-%M-%S"`"
            mkdir -p $log_dir_name
            log_dir=`realpath $log_dir_name`;;
        r)  rev="$OPTARG";;
        t)  tests="`tr "," " " <<<"$OPTARG"`" ;;
        n)  nm_off="yes";;
        g)  url="$OPTARG";;
        s)  use_git=false;;
        \?) exit 1;;
    esac
done

# Check for test suite lock
if [ -e .lock ]; then
    pid=`cat .lock`
    echo "The test suite is locked by process $pid." \
         "Someone might be using it right now."
    echo "Type 'unlock' if you wish to proceed anyway:"
    read -e input
    if [ "$input" != "unlock" ]; then
        exit 1
    fi
fi

# Lock the test suite
echo "$$" >.lock

# Clone the repo
export repo=`mktemp -d`
if $use_git ; then
    git clone $url $repo
else
    rsync -r $url $repo
fi

if $use_git ; then
    # Checkout the appropriate revision/tag
    if [ ! -z "$rev" ]; then
        pushd . >/dev/null
        cd $repo
        git checkout "$rev"
        popd >/dev/null
    else
        log "Revision not specified, using HEAD."
        rev="HEAD"
    fi
fi

# Load the proper config
#rm -rf ~/.lnst
#cp -r env ~/.lnst
cp -r env/* $repo/

# Scan the pool and prepare the machines in it
for machine in `ls -1 env/pool/`; do
    hostname=`get_hostname env/pool/$machine`

    # In case this script was killed and there are any slave processes
    # left hanging on the machine.
    ssh "root@$hostname" 'for p in `pgrep lnst-slave`; do kill -9 $p; done'

    # Create a temporary dir for the git tree to be tested
    remote_repo=`ssh "root@$hostname" "mktemp -d"`

    # Transfer the repo to the machine
    rsync -r --exclude "Logs" --exclude ".git" "$repo/" \
          "root@$hostname:$remote_repo"

    if [ ! -z $nm_off ]; then
        ssh "root@$hostname" "cd $remote_repo && echo \"use_nm = false\" >> lnst-slave.conf"
    fi

    # Start the slave process
    ssh -n -t -t "root@$hostname" "cd $remote_repo && ./lnst-slave" >/dev/null \
        2>/dev/null &
    pid=$!

    # Save the status (hostname, pid of the ssh session, repo path)
    # so we can cleanup things properly after the tests.
    if [ -z "$slave_status" ]; then
        slave_status="$hostname $pid $remote_repo"
    else
        slave_status="$hostname $pid $remote_repo
                      $slave_status"
    fi
done

sleep 1

summary="Summary:"

# Run the tests in the tests/ directory
print_separator

# In case the list of test names to run was omitted, run all of them
if [ -z "$tests" ]; then
    tests="`command ls -1 tests/ | grep -v '\.sh$' | sort -n`"
fi

for test_name in $tests; do
    test_dir=`realpath tests/$test_name`
    if [ -e "$test_dir/run.sh" ]; then
        logn "Running test #$test_name: "
        if [ -e $test_dir/desc ]; then
            while read line; do log "    $line"; done < $test_dir/desc
        else
            logn "\n"
        fi
        print_separator

        pushd . >/dev/null
        cd $test_dir

        chmod +x run.sh
        if [ -n "$log_dir" ]; then
            log_path="$log_dir/$test_name"
            mkdir -p "$log_path"

            # A bit of black magic in bash.
            # Explanation: http://bit.ly/1dxuMJI
            log "`PATH="$repo:$PATH" ./run.sh \
                > >(tee $log_path/stdout.log) \
                2> >(tee $log_path/stderr.log >&2)`"
        else
            PATH="$repo:$PATH" ./run.sh
        fi

        rv=$?

        popd >/dev/null

        print_separator
        if [ "$rv" -eq "0" ]; then
            log "Result #$test_name: PASS"
            summary=`echo -e "$summary\n    test #$test_name: PASS"`
        else
            log "Result #$test_name: FAIL"
            summary=`echo -e "$summary\n    test #$test_name: FAIL"`
            #break
        fi
        print_separator
    else
        log "Skipping test #$test_name, run.sh file not found."
        print_separator
        summary=`echo -e "$summary\n    test #$test_name: SKIPPED"`
    fi
done

log "$summary"
print_separator

sleep 1

# Cleanup
if [ -n "$slave_status" ]; then
    while read line; do
        hostname=`awk '{print $1}' <<<"$line"`
        pid=`awk '{print $2}' <<<"$line"`
        remote_repo=`awk '{print $3}' <<<"$line"`

        echo "kill $pid"
        kill $pid
        ssh -n "root@$hostname" "rm -r $remote_repo"
    done <<< "$slave_status"
fi

rm -rf $repo

rm -rf .lock
