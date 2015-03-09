# lnst-tests

**lnst-tests** is a regression test suite for the Linux Network Stack Test
Project. It contains a number of test cases and scenario to verify LNST
before releases and also to catch bugs and regressions.

In case you're interested in contributing to our project you should be
interested in this page as well since we won't be accepting contributions that
break any of our tests.

Currently there are two sets of tests that reside in our repository:
* smoke tests, located in ```recipes/smoke/```
* regression tests, located in ```regression-tests/```

It is important to note that all of these tests were created to test LNST
functionality for bugs. For this reason we assume that when running these
tests, they're being run on stable systems.

## Required Non-default Packages on slave machines

* rsync
* python-lxml (usually installed by default)
* python-pyroute2 (available in fedora repositories, epel6 and epel7)
* tar
* bzip2
* make
* gcc

## Smoke tests

Smoke tests were created to cover a wide area of basic LNST functionality, but
avoid testing for more complex/in-depth bugs.

As was mentioned before, smoke tests are located in the ```recipes/smoke/```
directory. Here you can find a subdirectory ```lib/``` and a python script
```generate-recipes.py```. The ```lib/``` directory contains 4 types of files:
* ```recipe-temp.xml``` recipe template file,
* ```conf-*.xml``` network configuration files,
* ```task-*.xml``` task definition files,
* ```variables.conf``` file.

The generate-recipes script loads the remplate file and fills it with two
configuration files and all the task files to create recipes for all possible
configuration combinations. The generated recipes are placed in the
```recipes/smoke/tests/``` directory.

Finally the variables file defines values for some variables (e.g. result of a
command), that are dependent on the combination of the configuration files.
When a recipe file is generated these variables are replaced with their
respective values.

To run these recipes you need to have 2 machines available in the pool you've
configured and you can use the following command:
```
lnst-ctl -d run recipes/smoke/tests/*
```

## Regression tests

Regression tests were created as a means to test for specific bugs that we have
already fixed. Our policy is to add a new regression test every time we fix a
more serious bug, however this isn't always possible due to different reasons.
If you find a bug in LNST and you want to contribute a patch that fixes it, it
is **highly recommended** to also create a regression test.

The directory structure for regression tests is as follows:
* ```regression-tests/``` is the main directory where everything related to
  regression tests is located.
* ```regression-tests/env/``` contains a LNST environment that is used by the
  regression tests. It contains a lnst-ctl configuration file and you're
  expected to create a machine pool directory here.
* ```regression-tests/tests/``` contains all the regression tests we currently
  have, isolated in their own directories that are numbered. You can also find
  the ```lib.sh``` file which contains definitions of some useful functions.
* ```regression-tests/tests/<test_number>/``` represents a regression test. It
  contains everything the tests needs. You can always find at least 2 files
  here: the ```run.sh``` script that executes the test, and ```desc``` which is
  a text file that contains the description of the test.
* ```regression-tests/run-test.sh``` is the script that controls the execution
  of regression tests.

Before running the regression tests, you need to prepare the environment. As
was mentioned the ```env/``` directory already contains the ```lnst-ctl.conf```
file. In addition to that you are also expected to create a machine pool
directory ```regression-tests/env/pool/``` and fill it with at least two slave
machine description files that should be used. Alternatively you can also use
your local configuration in ```~/.lnst/```, to do this you just need to use the
**-c** argument of the run-test.sh script.

In addition to this you need to ensure that the slave machines are running and
you have configured automatic ssh access to them. This is all the preparation
you need to do to run the regression tests, the ```run-test.sh``` script will
take care of synchronizing LNST to all the necessary machines, running
lnst-slave and lnst-ctl processes and cleaning them up in the end as well.

When it comes to running the tests you first need to change to the
```regression-tests``` directory and from here you have several options
depending on how you run the ```run-test.sh``` script.
```sh
Usage: ./run-test.sh [-c] [-r revision] [-l logdir] [-t list_of_tests] [-u url] [-n]
    -r revision       Test a specific git branch/rev/tag
                      Note: ignored when -s is used
    -l logdir         Save test results to a directory
    -t list_of_tests  Run only these tests
                      Example: -t 0,1,2 will run tests 0, 1, and 2
    -n                Disable use of NetworkManager on slavemachines
                      Note: enabled by default
    -u url            URL pointing to LNST repository that should be used
                      Note: git clone and checkout by default
    -s                use rsync instead of git
    -c                use user configuration
```
