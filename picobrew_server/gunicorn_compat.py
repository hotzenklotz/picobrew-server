"""Let gunicorn's pure-Python HTTP parser accept the Zymatic's requests.

Firmware 1.1.14 ends request lines and headers with a bare LF
("GET ... HTTP/1.0\\nHost: picobrew.com\\n..."). Gunicorn's Python parser only
splits on CRLF and waits for "\\r\\n\\r\\n" forever, so every machine request
times out. This patch rewrites bare LFs to CRLF in the request head of each
connection; the body and everything after the head pass through unchanged.

`gunicorn.conf.py` installs it. Gunicorn's optional C parser
(`gunicorn[fast]`) accepts bare LFs on its own.
"""

from gunicorn.http.unreader import SocketUnreader

HEAD_END = b"\r\n\r\n"


class HeadNormalizer:
    """Rewrite bare LFs to CRLF until the end of the request head."""

    def __init__(self) -> None:
        self.done = False
        self.tail = b""  # last bytes emitted, to match CRLF and the head end across chunks

    def feed(self, data: bytes) -> bytes:
        if self.done or not data:
            return data
        out = bytearray()
        for index, byte in enumerate(data):
            previous = out[-1:] if out else self.tail[-1:]
            if byte == 0x0A and previous != b"\r":
                out += b"\r\n"
            else:
                out.append(byte)
            if (self.tail + bytes(out[-4:]))[-4:] == HEAD_END:
                self.done = True
                return bytes(out) + data[index + 1 :]
        self.tail = (self.tail + bytes(out))[-4:]
        return bytes(out)


_original_chunk = SocketUnreader.chunk


def _normalized_chunk(self: SocketUnreader) -> bytes:
    normalizer = self.__dict__.setdefault("_picobrew_head", HeadNormalizer())
    return normalizer.feed(_original_chunk(self))


def install() -> None:
    SocketUnreader.chunk = _normalized_chunk
