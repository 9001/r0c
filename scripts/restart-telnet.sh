while true; do sleep 0.2; t=$(find ~/dev/r0c/ -type f -name '*.py' -printf '%T@\n' | sort -n | tail -n 1); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; sleep 1; telnet 127.0.0.1 2323; done

