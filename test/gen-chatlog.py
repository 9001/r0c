#!/usr/bin/env python2
# coding: utf-8
from __future__ import print_function


"""gen-chatlog.py: retr0chat chatlog generator"""
__version__ = "0.9"
__author__ = "ed <a@ocv.me>"
__credits__ = ["stackoverflow.com"]
__license__ = "MIT"
__copyright__ = 2018


import os
import time
import datetime
import calendar


te = time.time()
ts = te - 60 * 60 * 24 * 90

try:
    os.makedirs("../log/g/")
except:
    pass

with open("../log/g/0000-0000-000000", "wb") as f:
    last_date = None
    while ts < te:
        ht = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d, %H:%M:%S")
        date = ht[:10]

        if date != last_date:
            if last_date:
                fmt = "%Y-%m-%dT%H:%M:%S"
                mht = "{0}T00:00:00".format(date)
                mts = datetime.datetime.strptime(mht, fmt)
                # mts = mts.timestamp()   # BUG: assumes local time
                mts = calendar.timegm(mts.timetuple())
                print(mts)
                f.write(
                    u"{0} -- [36mday changed to [1m{1}\n".format(
                        hex(int(mts * 8.0))[2:].rstrip("L"), date
                    ).encode("utf-8")
                )
            last_date = date
        f.write(
            u"{0} gcpy {1}\n".format(hex(int(ts * 8.0))[2:].rstrip("L"), ht).encode(
                "utf-8"
            )
        )

        ts += 60 * 32 + 7

