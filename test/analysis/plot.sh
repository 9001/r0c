#!/bin/bash
set -e

tr -s ' ' > /dev/shm/r0c-perf.log

names="joins parts messages"

{
	echo "set term svg size 1600,1000"
	echo "set object rectangle from screen 0,0 to screen 1,1 behind fillcolor rgb 'white' fillstyle solid noborder"
	echo "set datafile separator ' '"
	echo "set xdata time"
	echo "set x2data time"
	echo "set timefmt '%s'"
	echo "set format x '%H'"
	echo "set format x2 '%M'"
	echo "set xlabel 'time, Hour/Minute'"
	echo "set ylabel 'actions per second'"
	echo "set grid xtics"
	echo "set xtics nooffset"
	echo "set x2tics nooffset"
	echo "set xtics 60"
	echo "set x2tics 60"
	echo "set mxtics 2"
	echo "set mx2tics 2"
	echo "set format y '%.0f'"
	
	n=1
	echo -n "plot "
	for x in $names
	do
		n=$((n+1))
		echo -n "'/dev/shm/r0c-perf.log' using 1:$n title '$x' with lines, "
	done
	echo
} |
sed 's/, $//' |
tee /dev/stderr |
gnuplot |
sed 's/stroke-linejoin:miter/stroke-linejoin:round/g' |
sed 's/stroke-width:1./stroke-width:2./g' |
sed 's/000<\/text>$/<\/text>/g' |
sed 's/font-size:12./font-size:16./g' > /dev/shm/r0c-perf.svg &&

{
	eog /dev/shm/r0c-perf.svg ||
	feh /dev/shm/r0c-perf.svg ||
	display /dev/shm/r0c-perf.svg ||
	gthumb /dev/shm/r0c-perf.svg ||
	xdg-open /dev/shm/r0c-perf.svg
}
