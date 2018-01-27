# `r0c` telnet server

* retr0chat, irc-like chat service for superthin clients
* MIT-Licensed, 2018-01-07, ed @ irc.rizon.net
* https://github.com/9001/r0c

![screenshot of telnet connected to a r0c server](doc/r0c.png)

## summary

* tries to be irssi
* runs on python 2.6, 2.7, 3.x
* supports telnet and netcat clients
* fallbacks for inhumane conditions
  * linemode
  * no vt100 / ansi escape codes

## supported clients

most to least recommended

| client | example |
| :---   | :---    |
| telnet | `telnet r0c.int` |
| socat  | `socat -,raw,echo=0 tcp:r0c.int:531` |
| netcat | `nc r0c.int 531` |
| bash   | `exec 147<>/dev/tcp/r0c.int/531; cat <&147 & while read -r x; do printf '%s\n' "$x" >&147; done` |
| powershell | [scrolling is kinda broken](clients/powershell.ps1)
