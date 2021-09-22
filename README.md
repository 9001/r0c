# `r0c` telnet server

* retr0chat, irc-like chat service for superthin clients [(on PyPI)](https://pypi.org/project/r0c/)
* MIT-Licensed, 2018-01-07, ed @ irc.rizon.net
* **[windows telnet 360 noscope](https://ocv.me/r0c.webm)** <- good video

![screenshot of telnet connected to a r0c server](docs/r0c.png)

* download the latest release (standalone): **[r0c.py](https://github.com/9001/r0c/releases/latest/download/r0c.py)**

## summary

imagine being stuck on ancient gear, in the middle of nowhere, on a slow connection between machines that are even more archaic than the toaster you're trying to keep from falling apart

retr0chat is the lightweight, no-dependencies, runs-anywhere solution for when life gives you lemons

* tries to be irssi
* zero dependencies on python 2.6, 2.7, 3.x
* supports telnet, netcat, /dev/tcp clients
* fallbacks for inhumane conditions
  * linemode
  * no vt100 / ansi escape codes

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

## firewall rules

telnet uses port 23 by default, so on the server you'll want to port-forward `23` to `2323` (and `531` to `1531` for plaintext):

```bash
iptables -A INPUT -p tcp --dport 23 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 531 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 2323 -m state --state NEW -j ACCEPT
iptables -A INPUT -p tcp --dport 1531 -m state --state NEW -j ACCEPT
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 23 -j REDIRECT --to-port 2323
iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 531 -j REDIRECT --to-port 1531
```

## documentation

not really but there is a [list of commands](docs/help-commands.md) and a [list of hotkeys](docs/help-hotkeys.md)
