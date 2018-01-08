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

