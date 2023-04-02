# `r0c` telnet server

* retr0chat, irc-like chat service for superthin clients [(on PyPI)](https://pypi.org/project/r0c/)
* MIT-Licensed, 2018-01-07, ed @ irc.rizon.net
* **[windows telnet 360 noscope](https://ocv.me/r0c.webm)** <- good video

![screenshot of telnet connected to a r0c server](docs/r0c.png)

* see [installation](#installation) or grab the latest release: **[r0c.py](https://github.com/9001/r0c/releases/latest/download/r0c.py)**

## summary

imagine being stuck on ancient gear, in the middle of nowhere, on a slow connection between machines that are even more archaic than the toaster you're trying to keep from falling apart

retr0chat is the lightweight, no-dependencies, runs-anywhere solution for when life gives you lemons

* tries to be irssi
* zero dependencies on python 2.6, 2.7, 3.x
* supports telnet, netcat, /dev/tcp, TLS clients
* [modem-aware](https://ocv.me/r0c-2400.webm); comfortable at 1200 bps
* fallbacks for inhumane conditions
  * linemode
  * no vt100 / ansi escape codes

## endorsements

* the german federal office for information security [does not approve](https://ocv.me/stuff/r0c-bsi.png)

## features

irc-like:
* public channels with persistent history (pgup/pgdn)
* private messages (`/msg acidburn hey`)
* nick completion with `Tab ↹`
* notifications (bell/visual) on hilights and PMs
* command subset (`/nick`, `/join`, `/part`, `/names`, `/topic`, `/me`)
* inline message coloring, see `/help`

technical:
* client behavior detection (echo, colors, charset, newline)
* message input with readline-like editing (arrow-left/right, home/end, backspace)
  * history of sent messages (arrow-up/down)
* bandwidth-conservative (push/pop lines instead of full redraws; scroll-regions)
* fast enough; 1'000 clients @ 200 msgs/sec

## windows clients

* use [putty](https://the.earth.li/~sgtatham/putty/latest/w32/putty.exe) in telnet mode
* or [the powershell client](clients/powershell.ps1)
* or enable `Telnet Client` in control panel `->` programs `->` programs and features `->` turn windows features on or off, then press WIN+R and run `telnet r0c.int`

putty is the best option;
* the powershell client is OK and no longer spammy as of windows 10.0.15063 (win10 1703 / LTSC)
* windows-telnet has a bug (since win7) where [non-ascii letters occasionally render but usually dont](https://ocv.me/stuff/win10-telnet.webm)
  * this is due to a buffer overflow in `telnet.exe`, so r0c will apply a rate-limit to avoid it
  * looks like messages larger than 512 bytes end up messing with the unicode glyphs area? or something

## linux clients

most to least recommended

| client | example |
| :---   | :---    |
| telnet | `telnet r0c.int` |
| socat  | `socat -,raw,echo=0 tcp:r0c.int:531` |
| bash   | [mostly internals](clients/bash.sh) |
| netcat | `nc r0c.int 531` |

you can even `exec 147<>/dev/tcp/r0c.int/531;cat<&147&while IFS= read -rn1 x;do [ -z "$x" ]&&x=$'\n';printf %s "$x">&147;done` (disconnect using `exec 147<&-; killall cat #sorry`)

## tls clients

if you enable TLS with `-tpt 2424` (telnet) and/or `-tpn 1515` (netcat) you can connect to r0c with TLS encryption using any of the following:

* `telnet-ssl -zssl -zsecure -zcacert=r0c.crt r0c.int 2424`
* `socat -,raw,echo=0 openssl:r0c.int:1515,cafile=cert.crt`
* `stty -icanon; ncat --ssl --ssl-trustfile r0c.crt -v r0c.int 1515`
* `stty -icanon; openssl s_client -CAfile ~/.r0c/cert.crt -connect r0c.int:1515`



# installation

just run **[r0c.py](https://github.com/9001/r0c/releases/latest/download/r0c.py)** and that's it (usually)

* or install through pypi (python3 only): `python3 -m pip install --user -U r0c`

you can run it as a service so it autostarts on boot:

* on most linux distros: [systemd service](docs/systemd/r0c.service) (automatically does port-forwarding)
* on alpine / gentoo: [openrc service](docs/openrc/r0c)
* on windows: [nssm](https://nssm.cc/) probably

## firewall rules

skip this section if:
* you are using the systemd service
* or you are running as root and do not have a firewall
* or you're on windows

telnet uses port 23 by default, so on the server you'll want to port-forward `23` to `2323` (and `531` to `1531` for plaintext):

```bash
iptables -A INPUT -p tcp --dport 23 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 531 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 2323 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 1531 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 2424 -m state --state NEW -j ACCEPT  # tls telnet
iptables -A INPUT -p tcp --dport 1515 -m state --state NEW -j ACCEPT  # tls netcat
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 23 -j REDIRECT --to-port 2323
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 531 -j REDIRECT --to-port 1531
```

(you'll have to do this on every reboot)

## documentation

not really but there is a [list of commands](docs/help-commands.md) and a [list of hotkeys](docs/help-hotkeys.md)
