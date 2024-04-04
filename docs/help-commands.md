**`/n`** or **`/nick`** changes your nickname  
`/n SparTacus`

**`/j`** or **`/join`** enters a chatroom  
`/j #music`

**`/p`** or **`/part`** leaves the chatroom

**`/t`** or **`/topic`** changes the channel topic  
`/t electro swing`

**`/me`**, the single mandatory feature anywhere  
`/me regrets adding this`

**`/m`** or **`/msg`** sends a private message  
`/msg SparTacus stop stealing my nick`

**`/q`** or **`/quit`** disconnects your client

# info

**`/help`** displays these help pages

**`/na`** or **`/names`** shows a list of people in the channel

**`/st`** or **`/status`** shows info about online users

**`/cfg`** shows client config

**`/cmap`** shows a list of colour codes

# control

**`/r`** or **`/redraw`** or `CTRL-L` redraws the screen to fix corruption, use this if things are glitchy after resizing the window

**`/sy`** and **`/sn`** turns on/off slowmo (avoids bug in telnet.exe on windows)

**`/b1`** and **`/b0`** turns on/off audible alerts when someone mentions your name;  
**`/b2`** makes it also trigger in active channels, and **`/b3`** beeps on any activity at all

**`/hsy`** and **`/hsn`** turns on/off logging of hilights/mentions to the status channel

**`/ey`** and **`/en`** turns on/off notifications on @all / @everyone in messages

**`/cy`** and **`/cn`** turns on/off colored nicknames

**`/my`** and **`/mn`** turns on/off wordwrap margins

**`/v`** or **`/view`** or `CTRL-N` toggles visibility of names in messages

**`/sw`** and **`/sh`** sets the terminal width/height in case the detection fails  
`/sw 80`  
`/sh 24`

**`/ss`** sets the PgUp/PgDn scroll amount

| | |
|-|-|
| `/ss 0`   | entire screen
| `/ss 10`  | 10 lines
| `/ss 50%` | half the screen

# navigation

**`/a`** or `CTRL-E` jumps to the oldest unread message across all your channels

**`/3`** jumps to your 3rd window

**`/u`**, **`/up`**, **`/d`**, **`/down`** are PageUp/PageDown for clients where the PgUp/PgDn buttons are busted

**`/l`** or **`/latest`** scrolls to the bottom of the chat window

**`/g`** or **`/goto`** jumps to a point in the past

| | |
|-|-|
| `/g 19:47`            | jump to time
| `/g 2018-01-21`       | jump to date
| `/g 2018-01-21 19:47` | jump to datetime
| `/g 3172`             | jump to message
| `/g 34%`              | jump to offset

# admin commands

**`/auth`** promotes you to administrator  
`/auth hunter2`

**`/fill`** floods the channel with messages  
`/fill 30 desu`

**`/bc`** broadcast message to all channels  
`/bc voting ends in 10`

**`/cls`** wipes channel scrollback (but keeps a copy on disk)

**`/sd`** shuts down the server

**`/mem`** dumps server memory to file

**`/repl`** drops server into a shell

**`/gc`** forces a garbage collection
