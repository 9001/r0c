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


# convert znc log to r0c format
f=2021-09-19; (echo 1 6147563b; cat $f.log | grep -E '^\[..:..:..\] <' | sed -r 's/^\[(..:..:..)\] <([^>]+)> /'$f'T\1Z \2 /' | while IFS=' ' read -r t s; do t=$(date +%s --date="$t"); printf '%x %s\n' "$((t*8))" "$s"; done) > ~/dev/r0c/log/chan/g/2021-0919-152443


# latin1
for cp in latin1 cp437; do printf "%02x" {32..255} | xxd -r -p | iconv -f $cp; echo; done > latin1-and-cp437
f = open('latin1-and-cp437', encoding='utf-8'); s = f.read(); f.close(); print('\n'.join(sorted("{:04x} {}".format(ord(x), x) for x in s)))


# statistics for attempted usernames / passwords
./format-wire-logs.sh | tee /dev/shm/wirefmt | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n


# check the accuracy for a set of badwords
./format-wire-logs.sh > /dev/shm/fwl1
bwds="root admin default support user password telnet vizxv Admin guest operator supervisor daemon service enable system manager baby netman telecom volition davox sysadm busybox tech 888888 666666 tech mg3500 merlin nmspw super setup HTTP/1 222222 xxyyzz synnet PlcmSpIp Glo"
#head -c 300 /dev/zero | tr '\0' '\n';  cp /dev/shm/fwl1 /dev/shm/fwl2; for bw in $bwds ; do ex="$(printf '\033\[0m  \.*P?\.*([^\.]+\.+)?'"${bw}")"; printf '%s\n' "$ex"; grep -vE "$ex" < /dev/shm/fwl2 > /dev/shm/fwl3 ; mv /dev/shm/fwl3 /dev/shm/fwl2 ; done; cat /dev/shm/fwl2 | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n
head -c 300 /dev/zero | tr '\0' '\n';  cp /dev/shm/fwl1 /dev/shm/fwl2; for bw in $bwds ; do grep -vE "$bw" < /dev/shm/fwl2 > /dev/shm/fwl3 ; mv /dev/shm/fwl3 /dev/shm/fwl2 ; done; cat /dev/shm/fwl2 | tee /dev/stderr | grep -E '^.\[' | sed -r "$(printf 's/.*\033\[0m  \.*P?\.*//;s/([^\.]*)\.*([^\.]*).*/\\1\\n\\2/')" | sort | uniq -c | sort -n


# log r0c stdout to file
cd ~/dev/r0c; stdbuf -oL python3 -um r0c 2323 1531 | tee log/sys-$(date +%Y-%m%d-%H%M%S)


# upgrade r0c
cd ~/dev/r0c; git checkout r0c/config.py; git pull origin; sed -ri 's/hunter2/amiga/;s/^(LOG_RX = False)/#\1/' r0c/config.py


# performance analysis
config.py: BENCHMARK = True
/c/Users/ed/AppData/Local/Programs/Python/Python39/python.exe -um r0c 2323 1531 k | tee plog
bash run-stress.sh 2323
python3 resample-log.py /dev/shm/r0c.log | bash plot.sh


# quick loadgen
m() { sleep 0.2; printf '%s\n' "$*"; };
cli() { (exec 147<>/dev/tcp/127.0.0.1/1531; timeout 10 cat >/dev/null <&147& (m n; m qwer asdf; m a; m y; m a; m '/join #g'; echo $$ >&2; for ((a=0;a<1000;a++)); do date; sleep 0.5; done) >&147); }
cln() { ps -ef | awk '/bash$/{print$2}' | while read p; do [ -S /proc/$p/fd/147 ] && kill $p; done; }
cln; for ((c=0;c<64;c++)); do cli & sleep 0.13; done


# simulate 2400 bps modem; listen on port 1923, relay to 2323, needs socat2
(cat >slowpipe; chmod 755 slowpipe) <<'EOF'
#!/bin/bash
bps=$1; fn=pf.$2
wav_hdr() { base64 -d <<<UklGRmT///9XQVZFZm10IBAAAAABAAEAgLsAAAB3AQACABAAZGF0YUD///8=; }
#rm -f $fn.{raw,wav}; mkfifo $fn.{raw,wav}; { wav_hdr; pv -qB1 -L97k <$fn.raw; } > $fn.wav & minimodem -rqf $fn.wav $bps & minimodem --tx-carrier -tqf $fn.raw $bps
rm -f $fn.{raw,wav}; mkfifo $fn.{raw,wav}; { wav_hdr; ffmpeg -re -hide_banner -flush_packets 1 -flags +low_delay -v warning -f s16le -ar 48000 -ac 1 -channel_layout mono -i - -flush_packets 1 -flags +low_delay -f s16le - <$fn.raw; } > $fn.wav & minimodem -rqf $fn.wav $bps & minimodem --tx-carrier -tqf $fn.raw $bps
EOF
/tmp/pe-socat2/bin/socat -d -d -d tcp4-l:1923,nodelay,reuseaddr "exec1:'./slowpipe 2400 r' % exec1:'./slowpipe 2400 t' | tcp:127.0.0.1:2323,nodelay"
./r0c.py -pt 2323 -pn 1531 --hex-rx --hex-tx
# ...manual cleanup if teardown fails:
ps aux | awk '/ cat pf\.[^\.]+\.[rw]aw| minimodem -[rt]f pf\.[^\.]+\.[rw]av |socat2\/bin/{print$2}' | xargs kill -9
# ...building socat2 on alpine:
sed -i '1i #include <stddef.h>' nestlex.c && sed -ri 's`netinet/if_ether`linux/if_ether`' sysincludes.h && sc_cv_getprotobynumber_r=2 ./configure --prefix=/tmp/pe-socat2 CFLAGS='-DNETDB_INTERNAL=\(-1\)' && make -j6 && make install
