"""Let gunicorn's pure-Python HTTP parser accept the Zymatic's requests.

Firmware 1.1.14 ends request lines and headers with a bare LF
("GET ... HTTP/1.0\\nHost: picobrew.com\\n..."). Gunicorn's Python parser only
splits on CRLF and waits for "\\r\\n\\r\\n" forever, so every machine request
times out. This patch rewrites bare LFs to CRLF in each request head; bodies
pass through unchanged.

`gunicorn_config.py` installs it, and installing it checks that gunicorn now
parses bare-LF requests, so an incompatible gunicorn release stops the server
at startup. Gunicorn's optional C parser (`gunicorn[fast]`) accepts bare LFs
on its own.
"""

import socket

import gunicorn
from gunicorn.config import Config
from gunicorn.http.message import Request
from gunicorn.http.parser import RequestParser
from gunicorn.http.unreader import Unreader

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


class HeadNormalizingUnreader:
    """Wrap a connection's unreader for the parse of one request head."""

    def __init__(self, unreader: Unreader) -> None:
        self.unreader = unreader
        self.normalizer = HeadNormalizer()

    def read(self, size: int | None = None) -> bytes:
        return self.normalizer.feed(self.unreader.read(size))

    def __getattr__(self, name: str) -> object:
        return getattr(self.unreader, name)


_original_parse = Request.parse


def _normalized_parse(self: Request, unreader: Unreader) -> bytes:
    # A fresh normalizer per request, so every head on a keep-alive or pipelined
    # connection is normalized. Bytes past the head are unread unchanged.
    return _original_parse(self, HeadNormalizingUnreader(unreader))


def self_test() -> None:
    """Parse bare-LF requests with gunicorn's Python parser, or raise RuntimeError.

    Fails loudly at startup if a gunicorn release no longer goes through the
    patched code, instead of letting every machine request time out.
    """
    cfg = Config()
    cfg.set("http_parser", "python")
    server, client = socket.socketpair()
    with server, client:
        server.settimeout(5)
        client.sendall(b"GET /first HTTP/1.1\nHost: a\n\nGET /second HTTP/1.1\nHost: a\n\n")
        client.shutdown(socket.SHUT_WR)
        try:
            parser = RequestParser(cfg, server, ("127.0.0.1", 0))
            paths = [next(parser).path, next(parser).path]
        except Exception as error:
            raise RuntimeError(f"gunicorn {gunicorn.__version__} rejects bare-LF requests: {error!r}") from error
    if paths != ["/first", "/second"]:
        raise RuntimeError(f"gunicorn {gunicorn.__version__} misparses bare-LF requests: {paths}")


def install() -> None:
    Request.parse = _normalized_parse
    self_test()
