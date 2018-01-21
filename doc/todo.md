done section is appended to every time something that was actually planned got finished

so bottom of this file is the latest completed task

the other lists are roughly sorted by importance (and additionally split in two at the *why tho* point)

# features: important

* store buffer in input history when hitting CUp/CDown
* notifications in topic bar

# features: whatever

* truncate chan hist when it gets 2big
* admin auth
* rate limiting
* nick colours

# bugs: important

# bugs: whatever

* py2 deadlocks on quit with threadcapture running
* channel cleanup doesn't happen unless user joins another channel after parting
* check for queue buildups in general

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
