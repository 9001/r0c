done section is appended to every time something that was actually planned got finished

so bottom of this file is the latest completed task

the other lists are roughly sorted by importance (and additionally split in two at the *why tho* point)

# features: important

* notifications in topic bar
* ^d to jump to hilight
* /names
* bell on by default, disable with /bn

# features: whatever

* admin auth
* rate limiting
* nick colours
* modals with command feedback

# bugs: important

* pings are case-sensitive
* can't message uppercase nicks
* text input glitches on colour input near screen edge
* copy/paste into putty on windows skips newlines ??

# bugs: whatever

* py2 deadlocks on quit with threadcapture running
* channel cleanup doesn't happen unless user joins another channel after parting
* check for queue buildups in general
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

