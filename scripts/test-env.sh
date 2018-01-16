#!/bin/bash

function k() {
	xdotool key --delay 10 $@
}

killall -9 telnet

for n in {1..4}; do
	xdotool search tn$n windowactivate sleep 0.3
	k control+c control+c Return control+c control+c Return 

	sleep 0.1; k t e l n e t space 1 2 7 period 0 period 0 period 1 space 2 3 2 3 Return
	sleep 0.1; k q w e r space a s d f space q w e r space a s d f Return
	sleep 0.1; k b 
	sleep 0.1; k y 
	sleep 0.1; k a 
	sleep 0.1; k slash j o i n space numbersign $n Return 
done



# set terminal title:
function wt() { printf '\033]0;%s\007' "$*"; }
