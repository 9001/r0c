#!/bin/bash

preferred_ports="23 531"
fallback_ports="2323 1531"

# use preferred ports if root,
# otherwise use fallback ports
[[ $(id -u) -eq 0 ]] &&
	ports="$preferred_ports" ||
	ports="$fallback_ports"

# start r0c
python -m r0c.__main__ $ports

# usually just "r0c" is enough,
# but python 2.6 needs the full "r0c.__main__"
