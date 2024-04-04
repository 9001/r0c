done section is appended to every time something that was actually planned got finished

so bottom of this file is the latest completed task

the other lists are roughly sorted by importance (and additionally split in two at the *why tho* point)

# features: important

* `nothing to see here`

# features: whatever

* rate limiting
* modals with command feedback
* filter bots somehow?

# features: mostly pointless

* notifications in topic bar

# bugs: important

* `nothing to see here`

# bugs: whatever

* wordwrap slices colour codes in half
* py2 deadlocks on quit with threadcapture running
* channel cleanup doesn't happen unless user joins another channel after parting
* colours don't carry over in wordwraps

# done

* config wizard
  * cp437
  * colors
  * stty

* ├┐ ┌┬┐ ┌ 
* redraw time every 5 seconds
* strip colors for non-vt100
* handle local echo  (good enough)
* fix far right column
* fix wordwrap for massive lines
* notifications in status bar
* full redraw statusbar on nick change
* /cmap
* /d
* 1f 00 00 doesnt get filtered from resize
* store state (channel messages)
* scrolling is wonky when loading small chatlogs
* deserialize takes 4gb ram
* color codes
* broadcast "day changed"
* store buffer in input history when hitting CUp/CDown
* truncate chan hist when it gets 2big
* ^d to jump to hilight
* /names
* pings are case-sensitive
* can't message uppercase nicks
* offer to skip wizard if IP has connected before
* bell on by default, disable with /b0
* preview colours in text input
* check if AYT can be used as ping/pong  (not really)
  * can use crazy options where you expect a nope in return and then get a nope every time you ask
* kick clients that are stuck in the config wizard for >10min

* tabcomplete (last-spoke order)
* suggest non-telnet clients to use the other interface (and vice versa)
* get terminal size from non-telnets
* copy/paste into putty on windows skips newlines ??
* non-vt100: /r and ^R don't clear hilights
* spinlock on incoming CSI sequences
* handle massive nicks
* some clients sending invalid utf8?
  * unparseable data before 303 in 303 total:
  * \xe2\xa3\xbf in messages
* verify crlf when loading cfg

* jump to ch0 on nick change, day change
* print nick on connect and disconnect
* admin auth
* write documentation orz

* check pwd dir
* check we're in $PATH
* nick colours
