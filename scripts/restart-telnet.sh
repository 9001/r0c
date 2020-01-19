#!/bin/bash
[ -e r0c/__main__.py ] || cd ..
[ -e r0c/__main__.py ] || cd ~/dev/r0c
[ -e r0c/__main__.py ] || exit 1

port=2323
[ $(id -u) -eq 0 ] &&
	port=23

while true; do sleep 0.2; t=$(find r0c -type f -name '*.py' -printf '%T@\n' | sort -n | tail -n 1); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; sleep 1; printf 'starting telnet'; telnet 127.0.0.1 $port; done

