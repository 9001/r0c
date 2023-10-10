#!/bin/bash
set -e

# fixed set of arguments to always give ttyd;
# * write-enable (needed by v1.7.4+)
# * don't reconnect if the user quits
# * disable some more stuff
# * the bifrost color scheme :^)
ttyd_fargs=(
    -W
    -t disableReconnect=true
    -t enableSixel=false
    -t enableTrzsz=false
    -t enableZmodem=false
    -t 'theme={"background":"#222","black":"#404040","red":"#f03669","green":"#b8e346","yellow":"#ffa402","blue":"#02a2ff","magenta":"#f65be3","cyan":"#3da698","white":"#d2d2d2","brightBlack":"#606060","brightRed":"#c75b79","brightGreen":"#c8e37e","brightYellow":"#ffbe4a","brightBlue":"#71cbff","brightMagenta":"#b67fe3","brightCyan":"#9cf0ed","brightWhite":"#fff"}'
)

# then the additional arguments to give ttyd by default;
# * listen on port 8023, http://127.0.0.1:8023/
# * listen on all interfaces (needed by v1.7.4+)
# * window title = r0c
# * dom works on phones (canvas/webgl is jank)
ttyd_args=(
    -p 8023
    -i 0.0.0.0
    -t titleFixed=r0c
    -t rendererType=dom
    -t disableResizeOverlay=true
)

# then the arguments to give r0c if nothing is given to the script;
# --ara is recommended because otherwise everyone will be admin
r0c_args=(
    --ara
)

# now, if this script is executed with any arguments at all, then the
# default r0c_args will be cleared and replaced with those, however
# you can also specify ttyd_args by separating them with "--";
# that way ttyd gets everything before that and r0c gets the rest:
#  ./webr0c.sh -p 8023 -- --ara -tpt 2424 -tpn 1515

if [ "$1" ]; then
    r0c_args=()
    while [ "$1" ]; do
        [ "$1" = -- ] && {
            ttyd_args=("${r0c_args[@]}")
            r0c_args=()
            shift
            continue
        }
        r0c_args+=("$1")
        shift
    done
fi

ttyd_args+=("${ttyd_fargs[@]}")  # append the fixed set of args

echo
echo " >>> will run ttyd with: ${ttyd_args[*]}"
echo
echo " >>> will run r0c with: ${r0c_args[*]}"
echo

########################################################################

# ensure we cleanup on exit
pids=()
trap 'kill ${pids[@]} 2>/dev/null;sleep 0.1' INT TERM EXIT

# first check if ttyd is installed system-wide,
# otherwise try ./ttyd.x86_64, and if that also fails
# just assume exactly one other binary is present
ttyd=$(command -v ttyd || echo ./ttyd.x86_64)
[ -e $ttyd ] || ttyd=./ttyd.*

if echo q | telnet -E -c; then
    # telnet seems to be working;
    # connect to port 23 if root, 2323 otherwise
    [ $(id -u) -eq 0 ] && p=23 || p=2323
    $ttyd "${ttyd_args[@]}" telnet -E -c 127.0.0.1 $p &
else
    echo "telnet not found; okay, using bash instead"
    # connect to port 531 if root, 1531 otherwise
    [ $(id -u) -eq 0 ] && p=531 || p=1531
    $ttyd "${ttyd_args[@]}" ./bashclient.sh 127.0.0.1 $p &
fi

pids+=($!)

# now it's time to start r0c,
# first check if installed system-wide,
# then try ./r0c.py, and panic if that also fails
if python3 -c 'import r0c' 2>/dev/null; then
    python3 -m r0c "${r0c_args[@]}" &
else
    python3 r0c.py "${r0c_args[@]}" &
fi

pids+=($!)

# figure out what port ttyd is listening on and print a helpful message
PORT=$(printf ' %s\n' "${ttyd_args[*]}" | sed -r 's/.* -p *([0-9]+).*/\1/; s/.*[^0-9].*//; s/^$/7681/')
printf '\n\033[32m >>> r0c available at http://127.0.0.1:%s/\n\033[0m      (and telnet and netcat too)\n' $PORT

# if either r0c or ttyd exits, kill the other
wait -n
kill ${pids[@]}
