#!/usr/bin/env python3
# coding: utf-8

import asyncio
import random
import struct
import signal
import time
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))
from r0c import util  # noqa: E402


"""astress.py: retr0chat stress tester (async edition)"""
__version__ = "0.9"
__author__ = "ed <a@ocv.me>"
__credits__ = ["stackoverflow.com"]
__license__ = "MIT"
__copyright__ = 2024


## config
##

NUM_CLIENTS = 1
NUM_CLIENTS = 750

CHANNELS = ['#1']
# CHANNELS = ["#1", "#2", "#3", "#4"]

EVENT_DELAY = 0.01
EVENT_DELAY = 0.005
EVENT_DELAY = 20
# EVENT_DELAY = None

VISUAL_CLIENT = True
# VISUAL_CLIENT = False

TELNET = False
TELNET = True

##
## config end


tsz = [80, 24]
tszb = struct.pack(">HH", *tsz)
# print(b2hex(tszb))
# sys.exit(0)


class Client(object):
    def __init__(self, core, port, behavior, n):
        self.core = core
        self.port = port
        self.behavior = behavior
        self.n = n
        self.explain = True
        self.explain = False
        self.dead = False
        self.stopping = False
        self.actor_active = False
        self.in_text = ""
        self.tx_only = False
        self.num_sent = 0
        self.pkt_sent = 0
        self.stage = "start"
        self.status = ""
        self.nick = "x"

    def close(self):
        self.stopping = True
        self.sck_rd.close()
        self.sck_wr.close()

    async def tx(self, txt):
        self.sck_wr.write(txt.encode("utf-8"))
        await self.sck_wr.drain()

    async def readloop(self):
        rd = self.sck_rd
        while not self.stopping:
            buf = await rd.read(8192)
            if self.tx_only:
                continue
            self.in_text += buf.decode("utf-8", "ignore")

    async def run(self):
        rd, wr = await asyncio.open_connection("127.0.0.1", self.port)
        self.sck_rd = rd
        self.sck_wr = wr

        self.actor_active = True
        print("client %d going up" % (self.n,))
        while not self.stopping:
            buf = await rd.read(8192)
            self.in_text += buf.decode("utf-8", "ignore")

            if self.stage == "start":
                termsize_rsp = b"\xff\xfa\x1f" + tszb + b"\xff\xf0"

                if "verify that your config" in self.in_text:
                    self.in_text = ""
                    wr.write(termsize_rsp)
                    await self.tx("n\n\n")

                if "type the text below, then hit [Enter] [Enter]:" in self.in_text:
                    self.stage = "qwer"
                    self.in_text = ""
                    wr.write(termsize_rsp)
                    for ch in "qwer asdf\n\n":
                        await self.tx(ch)
                        await asyncio.sleep(0.1)

                continue

            if self.stage == "qwer":
                test_pass = False

                if "your client is stuck in line-buffered mode" in self.in_text:
                    print("WARNING: r0c thinks we are linemode")
                    test_pass = True
                    await self.tx("a")

                if "text appeared as you typed" in self.in_text:
                    test_pass = True
                    await self.tx("b")

                if test_pass:
                    self.in_text = ""
                    self.stage = "color"
                continue

            if self.stage == "color":
                if "does colours work?" in self.in_text:
                    self.stage = "codec"
                    self.in_text = ""
                    await self.tx("y")
                continue

            if self.stage == "codec":
                if "which line looks like" in self.in_text:
                    self.stage = "getnick"
                    await self.tx("a")
                continue

            if self.stage == "getnick":
                ofs1 = self.in_text.find("H\033[0;36m")
                ofs2 = self.in_text.find(">\033[0m ")
                if ofs1 >= 0 and ofs2 == ofs1 + 8 + 6:
                    if not TELNET:
                        # print('sending vt100 termsize\n'*100)
                        await self.tx("\033[%d;%dR" % tsz)

                    self.nick = self.in_text[ofs2 - 6 : ofs2]
                    self.in_text = ""
                    await self.tx("/join %s\n" % (CHANNELS[0],))
                    self.stage = "ready"

                    self.status = "%s:start" % (self.nick,)

                    self.task_rd = asyncio.create_task(self.readloop())

                    if self.behavior == "flood_single_channel":
                        await self.flood_single_channel()
                        break

                    print("u wot")
                    break

        self.actor_active = False

    async def flood_single_channel(self):
        while "ok go" not in self.in_text:
            self.in_text = ""
            await asyncio.sleep(3)

        await asyncio.sleep(5 + EVENT_DELAY * random.random())

        self.tx_only = True
        while not self.stopping:
            await self.tx("%s\n" % (time.time(),))
            await asyncio.sleep(EVENT_DELAY)


class Core(object):
    def __init__(self):
        if len(sys.argv) < 2:
            print("need 1 argument:  telnet port")
            sys.exit(1)

        self.stopping = False
        self.clients = []
        self.ctasks = []

        signal.signal(signal.SIGINT, self.signal_handler)

    def print_status(self):
        msg = [x.status for x in self.clients]
        print(", ".join(msg))

    async def run(self):
        port = int(sys.argv[1])
        behaviors = ["flood_single_channel"] * int(NUM_CLIENTS)
        for n, behavior in enumerate(behaviors):
            cli = Client(self, port, behavior, n)
            self.ctasks.append(asyncio.create_task(cli.run()))
            self.clients.append(cli)
            await asyncio.sleep(0.07)
            if self.stopping:
                break

        print("  *  test is running")

        print_status = not VISUAL_CLIENT

        while not self.stopping:
            for n in range(5):
                await asyncio.sleep(1)
                if self.stopping:
                    break
            if print_status:
                self.print_status()

        print("  *  test ended")

    def shutdown(self):
        self.stopping = True

    def signal_handler(self, signal, frame):
        self.shutdown()


if __name__ == "__main__":
    core = Core()
    asyncio.run(core.run())


r_ = """
taskset -c 3 python3 -m r0c --bench -nc 9191
taskset -c 1 python3 test/astress.py 2323
taskset -c 2 python3 test/astress.py 2323
"""
