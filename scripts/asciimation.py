#!/usr/bin/env python3

import sys
import time
import socket
import threading


def getlines():
    n = 0
    slp = 0
    buf = b""
    with open('asciimation.txt', 'rb') as f:
        for ln in f:
            n += 1
            if n == 1:
                slp = int(ln.decode("ascii").rstrip())
                continue

            if ln.startswith(b"/"):
                ln = b"/" + ln

            buf += ln if len(ln) > 1 else b" \n"

            if n > 13:
                n = 0
                yield buf
                buf = b"/cls\n"
                time.sleep(slp / 16)


def readsocket(sck):
    while True:
        print(sck.recv(4096).decode("utf-8", "replace"))


def go():
    tgt = (sys.argv[1], int(sys.argv[2]))
    print(tgt)

    sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sck.connect(tgt)

    t = threading.Thread(target=readsocket, args=(sck,))
    t.daemon = True
    t.start()

    time.sleep(0.1)
    sck.sendall(b"ltn\n\n")  # send the linux-telnet cheatcode at the config wizard
    time.sleep(0.5)
    sck.sendall(b"ltn\n\n")  # and again, in case it was in the reuse-config prompt
    time.sleep(0.5)
    sck.sendall(b"\033[25;80R\n")  # reply to the console-size request that was sent
    time.sleep(0.5)
    sck.sendall(b"/n partybot\n")  # set a temp nickname until it starts
    time.sleep(0.5)
    sck.sendall(b"/j sw\n")  # join the channel it'll happen in
    time.sleep(0.5)
    for n in range(7, 0, -1):  # countdown 7 seconds
        sck.sendall(("%d...\n" % (n,)).encode("ascii"))
        time.sleep(1)
    sck.sendall(b"/n asciinema\n")  # set real nickname
    time.sleep(0.2)
    for msg in getlines():
        print(msg)
        sck.sendall(msg)  # send each "frame"
    time.sleep(2)


go()
