#!/bin/bash
echo this is not a shellscript
exit 1


# sort irc channels by number of participants (by parsing weechat logs)
cat irc.server.irc.freenode.net.weechatlog | sed -r 's/^....-..-.. ..:..:..[\t ]*--[\t ]*(#[^ ]*)\(([0-9]+)\).*/\2 \1/' | sort -n | grep -vE '^....-..-.. ..:..:..' | uniq -f 1


# proxy port 23 into userland
sudo socat TCP-LISTEN:23,range=127.0.0.1/24,reuseaddr,fork TCP:127.0.0.1:2323


# convert space -> tabs
find -maxdepth 1 -type f -iname \*.py | while read x; do sed -ri 's/^    /\t/' "$x"; done 
find -maxdepth 1 -type f -iname \*.py | while read x; do sed -ri 's/\t    /\t\t/' "$x"; done 


# visalize problematic combinations of whitespace
grep -RE "$(printf ' \t|\t ')" . 2>/dev/null | sed -r "$(printf 's/\\t/\033[1;34m----\033[0m/g;s/  /\033[43m  \033[0m/g;s/(["'"'"'])/\033[1;37;41m\\1\033[0m/g')" | less -R


# kill stress tests
ps ax | grep -E 'python[23]? .{0,2}stress\.py' | awk '{print $1}' | xargs kill


# irc log line length graph
cat radio.log | awk '{print length($0)}' | sort -n | uniq -c | awk '{print $2, $1}' | sort -n | awk '{ printf "%s: %" ($2/512) "s#\n", $1, "" }'
cat radio.log | awk 'length($0) > 30 && length($0) < 200 {print $0}' > radio.long


# statistics for attempted usernames / passwords
./format-wire-logs.sh | tee /dev/shm/wirefmt | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n


# check the accuracy for a set of badwords
./format-wire-logs.sh > /dev/shm/fwl1
bwds="root admin default support user password telnet vizxv Admin guest operator supervisor daemon service enable system manager baby netman telecom volition davox sysadm busybox tech 888888 666666 tech mg3500 merlin nmspw super setup HTTP/1 222222 xxyyzz synnet PlcmSpIp Glo"
#head -c 300 /dev/zero | tr '\0' '\n';  cp /dev/shm/fwl1 /dev/shm/fwl2; for bw in $bwds ; do ex="$(printf '\033\[0m  \.*P?\.*([^\.]+\.+)?'"${bw}")"; printf '%s\n' "$ex"; grep -vE "$ex" < /dev/shm/fwl2 > /dev/shm/fwl3 ; mv /dev/shm/fwl3 /dev/shm/fwl2 ; done; cat /dev/shm/fwl2 | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n
head -c 300 /dev/zero | tr '\0' '\n';  cp /dev/shm/fwl1 /dev/shm/fwl2; for bw in $bwds ; do grep -vE "$bw" < /dev/shm/fwl2 > /dev/shm/fwl3 ; mv /dev/shm/fwl3 /dev/shm/fwl2 ; done; cat /dev/shm/fwl2 | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n


# log r0c stdout to file
cd ~/dev/r0c; stdbuf -oL python2 -um r0c 2323 1531 | tee log/sys-$(date +%Y-%m%d-%H%M%S)


# upgrade r0c
cd ~/dev/r0c; git checkout r0c/config.py; git pull origin; sed -ri 's/hunter2/amiga/;s/^(LOG_RX = False)/#\1/' r0c/config.py


# performance analysis
config.py: BENCHMARK = True
stdbuf -oL python2 -m r0c 2323 1531 memes | tee /dev/shm/r0c.log
bash run-stress.sh 2323
python resample-log.py /dev/shm/r0c.log | bash plot.sh
