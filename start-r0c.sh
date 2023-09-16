#!/bin/bash

python3 -m r0c.__main__ "$@"

# additional arguments can be given to this batch file, for example
#   -pw goodpassword
#   -tpt 2424   (enable tls telnet on port 2424)
#   -tpn 1515   (enable tls netcat on port 1515)
#   --old-tls   (allow old/buggy software to connect (centos6, powershell))
