#!/bin/bash
echo this is not a shellscript
exit 1


# autorestart on quit, v1: single file  (run in separate terminals)
while true; do sleep 0.2; t=$(stat -c%Y /free/dev/chatsrv.py); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; ps ax | grep -E 'python[23] \./chatsrv' | awk '{print $1}' | while read pid; do kill -9 $pid; done; done
cd /free/dev/; while true; do for n in 2 3; do printf '\033[0m'; python$n ./chatsrv.py 23 4312; [[ $? -eq 1 ]] && sleep 1; sleep 0.2; done; done


# autorestart on quit, v2: multiple files  (run in separate terminals)
while true; do sleep 0.2; t=$(find ~/dev/r0c/ -maxdepth 1 -type f -printf '%T@\n' | sort -n | tail -n 1); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; ps ax | grep -E 'python[23] \./r0c' | awk '{print $1}' | while read pid; do kill -9 $pid; done; done
cd ~/dev/r0c; while true; do for n in 2 3; do printf '\033[0m'; python$n ./r0c.py 2323 4321; [[ $? -eq 1 ]] && sleep 1; sleep 0.2; done; done


# sort irc channels by number of participants (by parsing weechat logs)
cat irc.server.irc.freenode.net.weechatlog | sed -r 's/^....-..-.. ..:..:..[\t ]*--[\t ]*(#[^ ]*)\(([0-9]+)\).*/\2 \1/' | sort -n | grep -vE '^....-..-.. ..:..:..' | uniq -f 1


# proxy port 23 into userland
sudo socat TCP-LISTEN:23,range=127.0.0.1/24,reuseaddr,fork TCP:127.0.0.1:2323


# create backup
cd ~/dev && tar -czvf r0c-$(date +%Y-%m%d-%H%M).tgz --exclude='*.pyc' r0c 


# convert space -> tabs
find -maxdepth 1 -type f -iname \*.py | while read x; do sed -ri 's/^    /\t/' "$x"; done 
find -maxdepth 1 -type f -iname \*.py | while read x; do sed -ri 's/\t    /\t\t/' "$x"; done 

