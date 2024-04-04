# coding: utf-8
from __future__ import print_function
from .__init__ import EP, PY2, WINDOWS, COLORS, INTERP, unicode

import traceback
import threading
import socket
import struct
import time
import sys
import os
import re
import platform
import itertools
from datetime import datetime


print_mutex = threading.Lock()
if PY2:
    import __builtin__ as builtins
else:
    import builtins


HEX_WIDTH = 16

azAZ = u"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

BRI_256 = list(
    itertools.chain(
        range(35, 47),
        range(48, 52),
        range(70, 88),
        range(103, 124),
        range(132, 232),
    )
)


try:
    from datetime import datetime, timezone

    UTC = timezone.utc
except:
    from datetime import datetime, timedelta, tzinfo

    TD_ZERO = timedelta(0)

    class _UTC(tzinfo):
        def utcoffset(self, dt):
            return TD_ZERO

        def tzname(self, dt):
            return "UTC"

        def dst(self, dt):
            return TD_ZERO

    UTC = _UTC()


class Daemon(threading.Thread):
    def __init__(self, target, name=None, a=None):
        threading.Thread.__init__(self, target=target, args=a or (), name=name)
        self.daemon = True
        self.start()


def print(*args, **kwargs):
    args = list(args)
    try:
        if not COLORS and u"\033" in args[0]:
            args[0] = strip_ansi(args[0])
    except:
        pass

    with print_mutex:
        zd = datetime.now(UTC)
        t = "%06d " % (
            (zd.hour * 100 + zd.minute) * 100 + zd.second,
            # zd.microsecond // 1000
        )
        builtins.print(
            t + str(args[0] if args else u"").replace(u"\n", u"\n" + t),
            *args[1:],
            **kwargs
        )


def num(c):
    try:
        return int(c)
    except:
        return None


def t2ymd(dt, fmt):
    return fmt % (dt.year, dt.month, dt.day)


def t2ymd_hm(dt, fmt):
    return fmt % (dt.year, dt.month, dt.day, dt.hour, dt.minute)


def t2ymd_hms(dt, fmt):
    return fmt % (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def t2hms(dt, fmt):
    return fmt % (dt.hour, dt.minute, dt.second)


def t2hm(dt, fmt):
    return fmt % (dt.hour, dt.minute)


def b2hex(data):
    if PY2:
        return " ".join(map(lambda b: format(ord(b), "02x"), data))
    else:
        if type(data) is str:
            return " ".join(map(lambda b: format(ord(b), "02x"), data))
        else:
            return " ".join(map(lambda b: format(b, "02x"), data))


def hexdump(pk, prefix="", file=None):
    if file is not None:
        line_fmt = u"{0} {2}{3}{4}"
        hex_width = 4
        blk_width = 4
    else:
        line_fmt = u"{0}{1:8x}  {2}{3} {4}"
        hex_width = HEX_WIDTH
        blk_width = 8

    lpk = len(pk)
    ofs = 0
    hexofs = 0
    hexlen = 0
    hexstr = ""
    ascstr = ""
    ascstr_width = int(hex_width * 100 / 32.0 - 0.5)  # 32h = 100a, 16h = 50a
    while ofs < lpk:
        hexstr += b2hex(pk[ofs : ofs + blk_width])
        hexstr += " "
        if PY2:
            ascstr += "".join(
                map(
                    lambda b: b if ord(b) >= 0x20 and ord(b) < 0x7F else ".",
                    pk[ofs : ofs + blk_width],
                )
            )
        else:
            ascstr += "".join(
                map(
                    lambda b: chr(b) if b >= 0x20 and b < 0x7F else ".",
                    pk[ofs : ofs + blk_width],
                )
            )
        hexlen += blk_width
        ofs += blk_width

        if hexlen >= hex_width or ofs >= lpk:
            txt = line_fmt.format(
                prefix, hexofs, hexstr, u" " * (ascstr_width - len(hexstr)), ascstr
            )

            if file is not None:
                file.write((txt + u"\n").encode("utf-8"))
            else:
                print(txt)

            hexofs = ofs
            hexstr = ""
            hexlen = 0
            ascstr = ""
        else:
            hexstr += " "
            ascstr += " "


"""

def test_hexdump():
    try:
        from StringIO import StringIO as bio
    except:
        from io import BytesIO as bio

    v = b""
    for n in range(5):
        print()
        v += b"a"
        fobj = bio()
        hexdump(v, ">", fobj)
        print(fobj.getvalue().decode("utf-8").rstrip("\n") + "$")
        fobj.close()

    v = b""
    for n in range(18):
        print()
        v += b"a"
        hexdump(v, ">")

    sys.exit(0)

"""


def trunc(txt, maxlen):
    eoc = azAZ
    ret = u""
    clen = 0
    pend = None
    counting = True
    for input_ofs, ch in enumerate(txt):

        # escape sequences can never contain ESC;
        # treat pend as regular text if so
        if ch == u"\033" and pend:
            clen += len(pend)
            ret += pend
            counting = True
            pend = None

        if not counting:
            ret += ch
            if ch in eoc:
                counting = True
        else:
            if pend:
                pend += ch
                if pend.startswith(u"\033["):
                    counting = False
                else:
                    clen += len(pend)
                    counting = True
                ret += pend
                pend = None
            else:
                if ch == u"\033":
                    pend = unicode(ch)
                else:
                    ret += ch
                    clen += 1

        if clen >= maxlen:
            return [ret, txt[input_ofs:]]

    return [ret, u""]


# adapted from trunc
def strip_ansi(txt):
    eoc = azAZ
    ret = u""
    pend = None
    counting = True
    for ch in txt:

        # escape sequences can never contain ESC;
        # treat pend as regular text if so
        if ch == u"\033" and pend:
            ret += pend
            counting = True
            pend = None

        if not counting:
            if ch in eoc:
                counting = True
        else:
            if pend:
                pend += ch
                if pend.startswith(u"\033["):
                    counting = False
                else:
                    ret += pend
                    counting = True
                pend = None
            else:
                if ch == u"\033":
                    pend = u"{0}".format(ch)
                else:
                    ret += ch
    return ret


# adapted from trunc
def visual_length(txt):
    eoc = azAZ
    clen = 0
    pend = None
    counting = True
    for ch in txt:

        # escape sequences can never contain ESC;
        # treat pend as regular text if so
        if ch == u"\033" and pend:
            clen += len(pend)
            counting = True
            pend = None

        if not counting:
            if ch in eoc:
                counting = True
        else:
            if pend:
                pend += ch
                if pend.startswith(u"\033["):
                    counting = False
                else:
                    clen += len(pend)
                    counting = True
                pend = None
            else:
                if ch == u"\033":
                    pend = unicode(ch)
                else:
                    co = ord(ch)
                    # the safe parts of latin1 and cp437 (no greek stuff)
                    if (
                        co < 0x100  # ascii + lower half of latin1
                        or (co >= 0x2500 and co <= 0x25A0)  # box drawings
                        or (co >= 0x2800 and co <= 0x28FF)  # braille
                    ):
                        clen += 1
                    else:
                        # assume moonrunes or other double-width
                        clen += 2
    return clen


# 83% the speed of visual_length,
# good enough to stop maintaining it and swap w/ len(this)
def visual_indices(txt):
    eoc = azAZ
    ret = []
    pend_txt = None
    pend_ofs = []
    counting = True
    for n, ch in enumerate(txt):

        # escape sequences can never contain ESC;
        # treat pend as regular text if so
        if ch == u"\033" and pend_txt:
            ret.extend(pend_ofs)
            counting = True
            pend_txt = None
            pend_ofs = []

        if not counting:
            if ch in eoc:
                counting = True
        else:
            if pend_txt:
                pend_txt += ch
                pend_ofs.append(n)
                if pend_txt.startswith(u"\033["):
                    counting = False
                else:
                    ret.extend(pend_ofs)
                    counting = True
                pend_txt = None
                pend_ofs = []
            else:
                if ch == u"\033":
                    pend_txt = u"{0}".format(ch)
                    pend_ofs = [n]
                else:
                    ret.append(n)
    return ret


def sanitize_ctl_codes(aside):
    plain = u""
    passthru = (0x02, 0x0B, 0x0F)  # bold, color, reset
    for pch in aside:
        nch = ord(pch)
        # print('read_cb inner  {0} / {1}'.format(b2hex(pch.encode('utf-8', 'backslashreplace')), nch))
        if nch < 0x20 and nch not in passthru:
            print("substituting non-printable \\x{0:02x}".format(nch))
            plain += u"?"
        else:
            plain += pch
    return plain


def sanitize_fn(fn):
    for bad, good in [
        [u"<", u"＜"],
        [u">", u"＞"],
        [u":", u"："],
        [u'"', u"＂"],
        [u"/", u"／"],
        [u"\\", u"＼"],
        [u"|", u"｜"],
        [u"?", u"？"],
        [u"*", u"＊"],
        [u"'", u"＇"],  # shell-safety
        [u"`", u"｀"],  # shell-safety
    ]:
        fn = fn.replace(bad, good)

    if WINDOWS:
        bad = [u"con", u"prn", u"aux", u"nul"]
        for n in range(1, 10):
            bad += u"com{0} lpt{0}".format(n).split(u" ")

        if fn.lower() in bad:
            fn = u"_" + fn

    return fn


FOREGROUNDS = {}
for luma, chars in enumerate([u"01234567", u"89abcdef"]):
    for n, ch in enumerate(chars):
        FOREGROUNDS[ch] = u"\033[{0};3{1}".format(luma, n)

BACKGROUNDS = {}
for n, ch in enumerate(u"01234567"):
    BACKGROUNDS[ch] = u";4{0}".format(n)


def convert_color_codes(txt, preview=False):
    foregrounds = FOREGROUNDS
    backgrounds = BACKGROUNDS
    scan_from = 0
    while txt:
        ofs = txt.find(u"\x0b", scan_from)
        if ofs < 0:
            break

        scan_from = ofs + 1

        fg = None
        if len(txt) > ofs + 1:
            fg = txt[ofs + 1]

        bg = None
        if len(txt) > ofs + 3 and txt[ofs + 2] == u",":
            bg = txt[ofs + 3]

        if fg in foregrounds:
            fg = foregrounds[fg]
        else:
            fg = None
            bg = None  # can't set bg without valid fg

        if bg in backgrounds:
            bg = backgrounds[bg]
        else:
            bg = None

        resume_txt = ofs + 1
        if fg:
            resume_txt += 1
            scan_from = len(fg) + 1
        if bg:
            resume_txt += 2
            scan_from += len(bg)

        preview_k = u""
        if preview:
            resume_txt = ofs + 1
            if fg:
                preview_k = u"K"

        if fg and bg:
            txt = u"%s%s%sm%s%s" % (txt[:ofs], fg, bg, preview_k, txt[resume_txt:])
        elif fg:
            txt = u"%s%sm%s%s" % (txt[:ofs], fg, preview_k, txt[resume_txt:])
        else:
            txt = u"%sK%s" % (txt[:ofs], txt[resume_txt:])

    scan_from = 0
    is_bold = False
    while txt:
        ofs = txt.find(u"\x02", scan_from)
        if ofs < 0:
            break

        scan_from = ofs + 1
        is_bold = not is_bold
        txt = u"%s\033[%dm%s%s" % (
            txt[:ofs],
            1 if is_bold else 22,
            u"B" if preview else u"",
            txt[scan_from:],
        )

    scan_from = 0
    while txt:
        ofs = txt.find(u"\x0f", scan_from)
        if ofs < 0:
            break

        scan_from = ofs + 1
        txt = u"%s\033[0m%s%s" % (
            txt[:ofs],
            u"O" if preview else u"",
            txt[scan_from:],
        )

    return txt


FG_TO_IRC = {}
FG_FROM_IRC = {}
for n, ch in enumerate(u"f0429153ba6ecd87"):
    FG_FROM_IRC[n] = u"\x0b%s" % (ch,)
    FG_TO_IRC[ch] = u"\x03%02d" % (n,)

BG_TO_IRC = {}
BG_FROM_IRC = {}
for n, ch in enumerate(u"7042115332664507"):
    BG_FROM_IRC[n] = u",%s" % (ch,)
    BG_TO_IRC[ch] = u",%02d" % (n,)

IRC_COLOR_RE = re.compile("^([0-9]{1,2})(,[0-9]{1,2})?")


def color_to_irc(txt):
    # mostly copy-pasted from `convert_color_codes`
    foregrounds = FG_TO_IRC
    backgrounds = BG_TO_IRC
    scan_from = 0
    while txt:
        ofs = txt.find(u"\x0b", scan_from)
        if ofs < 0:
            break

        scan_from = ofs + 1

        fg = None
        if len(txt) > ofs + 1:
            fg = txt[ofs + 1]

        bg = None
        if len(txt) > ofs + 3 and txt[ofs + 2] == u",":
            bg = txt[ofs + 3]

        if fg in foregrounds:
            fg = foregrounds[fg]
        else:
            fg = None
            bg = None  # can't set bg without valid fg

        if bg in backgrounds:
            bg = backgrounds[bg]
        else:
            bg = None

        resume_txt = ofs + 1
        if fg:
            resume_txt += 1
            scan_from = len(fg) + 1
        if bg:
            resume_txt += 2
            scan_from += len(bg)

        if fg and bg:
            txt = u"%s%s%s%s" % (txt[:ofs], fg, bg, txt[resume_txt:])
        elif fg:
            txt = u"%s%s%s" % (txt[:ofs], fg, txt[resume_txt:])
        else:
            txt = u"%s\x03%s" % (txt[:ofs], txt[resume_txt:])

    # irc bold  == r0c, \x02
    # irc reset == r0c, \x0f
    return txt


def color_from_irc(txt):
    fgs = FG_FROM_IRC
    bgs = BG_FROM_IRC
    ptn = IRC_COLOR_RE
    scan_from = 0
    while txt:
        ofs = txt.find(u"\x03", scan_from)
        if ofs < 0:
            break

        fg = bg = ""
        scan_from = ofs + 1
        m = ptn.search(txt[scan_from : scan_from + 5])
        if m:
            i = int(m.group(1))
            if i < 16:
                fg = fgs[i]
                if m.group(2):
                    i = int(m.group(2)[1:])
                    if i < 16:
                        bg = bgs[i]

                scan_from += len(m.group(0 if bg else 1))

        if bg:
            txt = u"%s%s%s%s" % (txt[:ofs], fg, bg, txt[scan_from:])
        elif fg:
            txt = u"%s%s%s" % (txt[:ofs], fg, txt[scan_from:])
        else:
            txt = u"%s\x0f%s" % (txt[:ofs], txt[scan_from:])
            # no easy/cheap way to encode "keep boldness and reset color";
            # `convert_color_codes` would then eat any following a..f

    return txt


"""

def visualize_all_unicode_codepoints_as_utf8():
    stats = [0] * 256
    nmax = sys.maxunicode + 1
    print("collecting all codepoints until {0}d, 0x{1:x}".format(nmax, nmax))

    if PY2:
        to_unicode = unichr  # noqa: F821
        from_char = ord
    else:
        to_unicode = chr
        from_char = int

    for n in range(nmax):
        if n % 0x10000 == 0:
            print(
                "at codepoint {0:6x} of {1:6x},  {2:5.2f}%".format(
                    n, nmax, (100.0 * n) / nmax
                )
            )
        ch = to_unicode(n)

        try:
            bs = ch.encode("utf-8")
        except:
            # python2 allows encoding ud800 as \xed\xa0\x80 which is an illegal sequence in utf8;
            # python -c "for x in unichr(0xd800).encode('utf-8'): print '{0:2x}'.format(ord(x))"
            continue

        for b in bs:
            stats[from_char(b)] += 1

    print()
    for i, n in enumerate(stats):
        v = n
        if v == 0:
            v = "illegal value"
        elif v == 1:
            v = "single-use value"
        print("byte 0x{0:2x} occurences: {1}".format(i, v))
    print()


# visualize_all_unicode_codepoints_as_utf8()

"""


def wrap(txt, maxlen, maxlen2):
    words = txt.rstrip().split()
    ret = []
    for word in words:
        if len(word) * 2 < maxlen or visual_length(word) < maxlen:
            ret.append(word)
        else:
            while visual_length(word) >= maxlen:
                ret.append(word[: maxlen - 1] + u"-")
                word = word[maxlen - 1 :]
            if word:
                ret.append(word)

    words = ret
    ret = []
    ln = u""
    spent = 0
    for word in words:
        wl = visual_length(word)
        if spent + wl > maxlen:
            ret.append(ln[1:])
            maxlen = maxlen2
            spent = 0
            ln = u""
        ln += u" " + word
        spent += wl + 1
    if ln:
        ret.append(ln[1:])

    return ret


def hardwrap(txt, maxlen, vt100):
    # safer than wrap() since it discards escape sequences, making it splittable anywhere
    ret = []
    prefix = u""
    txt = strip_ansi(txt)
    while txt:
        ret.append(prefix + txt[:maxlen])
        txt = txt[maxlen:]
        if vt100:
            prefix = u"\033[36m"

    return ret


def whoops(extra=None):
    msg = r"""
             __
   _      __/ /_  ____  ____  ____  _____
  | | /| / / __ \/ __ \/ __ \/ __ \/ ___/
  | |/ |/ / / / / /_/ / /_/ / /_/ (__  )
  |__/|__/_/ /_/\____/\____/ .___/____/
                          /_/"""
    exc = traceback.format_exc()
    if exc.startswith("None"):
        exc = "".join(traceback.format_stack()[:-1])
    msg = "{0}\r\n{1}\r\n{2}</stack>".format(msg[1:], exc.rstrip(), "-" * 64)
    print(msg)
    if extra:
        print("  {0}\n{1}\n".format(extra, "-" * 64))


def t_a_a_bt():
    ret = []
    for tid, stack in sys._current_frames().items():
        ret.append(u"\r\nThread {0} {1}".format(tid, "=" * 64))
        for fn, lno, func, line in traceback.extract_stack(stack):
            ret.append(u'  File "{0}", line {1}, in {2}'.format(fn, lno, func))
            if line:
                ret.append(u"    {0}".format(line.strip()))
    return u"\r\n".join(ret)


thread_monitor_enabled = False


def monitor_threads():
    global thread_monitor_enabled
    if thread_monitor_enabled:
        return
    thread_monitor_enabled = True

    def stack_collector():
        while True:
            print("capturing stack")
            time.sleep(5)
            txt = t_a_a_bt()
            with open("r0c.stack", "wb") as f:
                f.write(txt.encode("utf-8"))

    Daemon(stack_collector, "stk_col")


def host_os():
    py_ver = ".".join([str(x) for x in sys.version_info])
    ofs = py_ver.find(".final.")
    if ofs > 0:
        py_ver = py_ver[:ofs]

    bitness = struct.calcsize("P") * 8
    host_os = platform.system()
    return "{0} on {1}{2}".format(py_ver, host_os, bitness)


def py26_threading_event_wait(event):
    """
    threading.Event.wait() is broken on py2.6;
    with multiple subscribers it doesn't always trigger
    """
    if (
        sys.version_info[:2] != (2, 6)
        or INTERP != "CPython"
        or "_Event__flag" not in event.__dict__
    ):
        return

    def nice_meme(timeout=None):
        if event._Event__flag:
            return True

        time.sleep(0.2)
        return event._Event__flag

    event.wait = nice_meme


def close_sck(sck):
    # could go fancy and grab the siocoutq stuff from copyparty but ehh
    try:
        sck.shutdown(socket.SHUT_WR)
        time.sleep(0.1)
        sck.shutdown(socket.SHUT_RDWR)
    except:
        pass
    finally:
        sck.close()


"""
# ---------------------------------------------------------------------
# dumping ground for mostly useless code below


def test_ansi_annotation():
    rangetype = range
    try:
        rangetype = xrange  # noqa: F405,F821
    except:
        pass
    ansi_txt = (
        "\033[1;33mHello \033[1;32mWorld\033[0m! This \033[7mis\033[0m a test.\033[A"
    )
    ansi_txt = "\033[mf\033[s\033[w\033[has\033[3451431613gt\033[m \033[s\033[g\033[s\033[g\033[s\033[gcod\033[me\033[x"
    rv = visual_indices(ansi_txt)
    print(" ".join(ansi_txt.replace("\033", "*")))
    print(" ".join([str(x % 10) for x in rangetype(len(ansi_txt))]))
    print(" ".join([str(x) for x in rv]))
    print("{0} {1}".format(visual_length(ansi_txt), len(rv)))
    visual = ""
    for ofs in rv:
        visual += ansi_txt[ofs]
    print("[{0}]".format(visual))

    for outer_n in rangetype(3):

        t0 = time.time()
        for n in rangetype(100000):
            rv = visual_indices(ansi_txt)
        print(str(time.time() - t0))

        t0 = time.time()
        for n in rangetype(100000):
            rv = visual_length(ansi_txt)
        print(str(time.time() - t0))
"""
