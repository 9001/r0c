cd ~/dev/r0c; while true; do for n in 2 3; do printf '\033[0m'; python$n ./r0c.py 2323 4321; [[ $? -eq 1 ]] && sleep 1; sleep 0.2; done; done

