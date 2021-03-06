# coding: utf-8
from __future__ import print_function
from .__init__ import EP
from . import config as Config
from . import util as Util
from . import ivt100 as Ivt100

import time

print = Util.print


if __name__ == "__main__":
    raise RuntimeError(
        "\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}".format(
            "*" * 72
        )
    )


class NetcatServer(Ivt100.VT100_Server):
    def __init__(self, host, port, world, other_if):
        Ivt100.VT100_Server.__init__(self, host, port, world, other_if)
        self.user_config_path = EP.log + "cfg.netcat"

    def gen_remote(self, socket, addr, user):
        return NetcatClient(self, socket, addr, self.world, user)


class NetcatClient(Ivt100.VT100_Client):
    def __init__(self, host, socket, address, world, user):
        Ivt100.VT100_Client.__init__(self, host, socket, address, world, user)

        self.looks_like_telnet = {
            b"\xff\xfe": 1,
            b"\xff\xfd": 1,
            b"\xff\xfc": 1,
            b"\xff\xfb": 1,
        }
        # trick telnet into revealing itself:
        # request client status and location
        self.replies.put(b"\xff\xfd\x05\xff\xfd\x17")

    def handle_read(self):
        with self.world.mutex:
            if self.dead:
                print("XXX reading when dead")
                return

            try:
                data = self.socket.recv(8192)
                if not data:
                    raise Exception()
            except:
                if not self.dead:
                    self.host.part(self)
                return

            if Config.HEXDUMP_IN:
                Util.hexdump(data, "-->>")

            if self.wire_log and Config.LOG_RX:
                self.wire_log.write(
                    "{0:.0f}\n".format(time.time() * 1000).encode("utf-8")
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
                src = u"{0}".format(self.in_bytes.decode(self.codec))
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
