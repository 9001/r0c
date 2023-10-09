# coding: utf-8
from __future__ import print_function
from .__init__ import EP, unicode
from . import util as Util
from . import ivt100 as Ivt100

import time

print = Util.print


class NetcatServer(Ivt100.VT100_Server):
    def __init__(self, host, port, world, other_if, tls):
        Ivt100.VT100_Server.__init__(self, host, port, world, other_if, tls)
        ucp = "{0}cfg.{1}netcat".format(EP.log, "tls-" if tls else "")
        self.user_config_path = ucp

    def gen_remote(self, sck, addr, user):
        return NetcatClient(self, sck, addr, self.world, user)


class NetcatClient(Ivt100.VT100_Client):
    def __init__(self, host, sck, address, world, user):
        Ivt100.VT100_Client.__init__(self, host, sck, address, world, user)

        self.looks_like_telnet = {
            b"\xff\xfe": 1,
            b"\xff\xfd": 1,
            b"\xff\xfc": 1,
            b"\xff\xfb": 1,
        }
        # trick telnet into revealing itself:
        # request client status and location
        self.replies.append(b"\xff\xfd\x05\xff\xfd\x17")

    def handle_read(self):
        with self.world.mutex:
            if self.dead:
                print("XXX reading when dead")
                return

            try:
                data = self.sck.recv(8192)
                if not data:
                    raise Exception()
            except:
                if not self.dead:
                    self.host.part(self)
                return

            if self.ar.hex_rx:
                Util.hexdump(data, "-->>")

            if self.wire_log and self.ar.log_rx:
                self.wire_log.write(
                    unicode(int(time.time() * 1000)).encode("utf-8") + b"\n"
                )
                Util.hexdump(data, ">", self.wire_log)

            self.in_bytes += data

            if b"\xff" in data:
                ofs = 0
                while ofs >= 0:
                    ofs = data.find(b"\xff", ofs)
                    if ofs < 0:
                        break
                    if data[ofs : ofs + 2] in self.looks_like_telnet:
                        self.num_telnet_negotiations += 1
                    ofs = ofs + 1
            try:
                src = unicode(self.in_bytes.decode(self.codec))
                self.in_bytes = self.in_bytes[0:0]

            except UnicodeDecodeError as uee:
                uee.start += self.uee_offset
                if len(self.in_bytes) < uee.start + 6:
                    print(
                        "need more data to parse unicode codepoint at {0} in {1}".format(
                            uee.start, len(self.in_bytes)
                        )
                    )
                    Util.hexdump(self.in_bytes[-8:], "XXX ")
                    src = u"{0}".format(self.in_bytes[: uee.start].decode(self.codec))
                    self.in_bytes = self.in_bytes[uee.start :]
                else:
                    # it can't be helped
                    print("warning: unparseable data:")
                    Util.hexdump(self.in_bytes, "XXX ")
                    src = u"{0}".format(
                        self.in_bytes[: uee.start].decode(
                            self.codec, "backslashreplace"
                        )
                    )
                    self.in_bytes = self.in_bytes[0:0]  # todo: is this correct?

            self.in_text += src

            if self.wizard_stage is not None and len(self.in_text_full) < 1024:
                self.in_text_full += src

            self.read_cb(False, len(src))
