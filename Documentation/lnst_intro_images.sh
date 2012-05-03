#!/bin/bash

FILES="real-hardware-setup machineconfig-netconfig-mapping"

if [ $# -gt 0 ] && [ $1 == "clean" ]; then
    echo "Removing png files for LNSTIntro"
    for f in $FILES; do
        rm -f $f.png
    done
else
    for f in $FILES; do
        /usr/bin/dia -e $f.png $f.dia
    done
fi

