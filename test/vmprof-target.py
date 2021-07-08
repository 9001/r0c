#!/usr/bin/env python3

import sys
import runpy

sys.path.insert(0, ".")
sys.argv = ["r0c", "2323", "1531", "k"]
runpy.run_module("r0c", run_name="__main__")


"""
python3.9 -m pip install --user vmprof
python3.9 -m vmprof --lines -o vmprof.log test/vmprof-target.py
~/.local/bin/vmprofshow vmprof.log tree | grep -vF '[1m  0.'
"""
