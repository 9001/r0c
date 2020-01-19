#!/bin/bash
set -e

# --------------------------------------------
# tcp plaintext client without linebuffering
# --------------------------------------------
# uses bash internals wherever possible,
# let me know if I missed some opportunities
# --------------------------------------------

debug=''
#debug=1

cat_pid=''

function ctrl_c()
{
	kill $cat_pid
	exit 0
}

function connect()
{
	# hook ctrl-c for cleanup
	trap ctrl_c INT

	# open the tcp connection
	exec 147<>/dev/tcp/$1/$2
	
	# dump socket to stdout
	cat <&147 & cat_pid=$!

	# read keyboard and send each key to the socket
	while IFS= read -rn1 x
	do
		[ "x$x" == "x" ] &&
			x=$'\n'
		
		[ $debug ] &&
		{
			printf '%s' "$x" |
			tee /dev/stderr 2>&1 >&147 |
			xxd -c8 -g1 >> /dev/shm/r0c-log
		} ||
		printf '%s' "$x" >&147
	done
}

[ "x$2" == x ] &&
{
	echo
	echo "   r0c client (bash edition)"
	echo "     need argument 1:  r0c server ip or hostname"
	echo "     need argument 2:  r0c server port"
	echo
	exit 1
}

connect $1 $2
