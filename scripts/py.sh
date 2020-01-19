#!/bin/bash
[ -e r0c/__main__.py ] || cd ..
[ -e r0c/__main__.py ] || cd ~/dev/r0c
[ -e r0c/__main__.py ] || exit 1

ports='2323 1531'
[ $(id -u) -eq 0 ] &&
	ports='23 531'

while true
do
	for n in 2 3
	do
		printf '\n\033[0;1;33mstarting py%s\033[0m\n\n' $n
		sleep 0.5 || break

		python$n -m r0c $ports
		
		[ $? -eq 1 ] &&
			sleep 1
	done
done

