#!/bin/bash
[ -e r0c/__main__.py ] || cd ..
[ -e r0c/__main__.py ] || cd ~/dev/r0c
[ -e r0c/__main__.py ] || exit 1

while true; do sleep 0.2; t=$(find r0c -type f -name '*.py' -printf '%T@\n' | sort -n | tail -n 1); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; ps ax | grep -E 'python[23] -m r0c' | awk '{print $1}' | while read pid; do kill -9 $pid; killall -9 telnet; done; done

