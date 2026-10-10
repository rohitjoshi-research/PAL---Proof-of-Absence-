#!/bin/sh
set -e
cd "$(dirname "$0")"
run() { cut=$1; mode=$2; n=$3; h=$((n/2)); python3 render.py frames $cut $mode 0 $h & python3 render.py frames $cut $mode $h $n & wait; echo "done $cut $mode"; }
run full wide 3501
run social square 1870
run social wide 1870
