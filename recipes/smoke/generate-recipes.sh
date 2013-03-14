#!/bin/bash

# LNST Smoke Tests
# Author:  Radek Pazdera <rpazdera@redhat.com>
# License: GNU GPLv2

# This script will generate a set of recipes for assessing the very basic
# functionality of LNST.

DIR="tests/"
LIB="../lib"

echo "[LNST Smoke Tests]"

echo -n "Creating '$DIR' directory for the recipes..."
mkdir -p $DIR
cd $DIR
echo -e "[DONE]"

sequences=""
for seq in `ls -1 $LIB/seq-*`; do
    echo "Found command sequence $seq"
    sequences="$sequences\n    <command_sequence source=\"$seq\"/>"
done

CONF_FILES=`ls -1 $LIB/conf-*`
for conf in $CONF_FILES; do
    echo "Found configuration $conf"
done

for machine1 in $CONF_FILES; do
    for machine2 in $CONF_FILES; do
        name1=`echo -n "$machine1" | head -c -4 | cut -c 13-`
        name2=`echo -n "$machine2" | head -c -4 | cut -c 13-`
        recipe_name="recipe-$name1-$name2.xml"
        echo -ne "Generating $DIR$recipe_name..."
        cat "$LIB/recipe-temp.xml" | \
                sed "s|#CONF1#|$machine1|g" | \
                sed "s|#CONF2#|$machine2|g" | \
                sed "s|#SEQUENCES#|$sequences|g" > "$recipe_name"

        echo -e "[DONE]"
    done
done

echo ""

echo "To run these recipes, you need to have a pool prepared with at"
echo "least two machines. Both of them must have at least two test"
echo "interfaces connected to the same network segment."

echo ""

echo "   +-----------+          +--------+          +-----------+"
echo "   |           |----------|        |----------|           |"
echo "   |  Machine  |          | Switch |          |  Machine  |"
echo "   |     1     |----------|        |----------|     2     |"
echo "   |           |          +--------+          |           |"
echo "   +-----------+                              +-----------+"

echo -e "\nYou can execute the set using the following command:"
echo "    ./lnst-ctl -d recipes/smoke/tests/ run"
