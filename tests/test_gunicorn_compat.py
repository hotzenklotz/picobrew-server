import os
import runpy
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("fcntl", reason="gunicorn does not run on Windows")

from picobrew_server.gunicorn_compat import HeadNormalizer, install, self_test  # noqa: E402

ROOT = Path(__file__).parents[1]
# Byte-for-byte what firmware 1.1.14 sends (eth_printHttpTrailer / net_sendHostHeaderTail).
FIRMWARE_REQUEST = (
    b"GET /API/checksync?user=dd945a43414a52cb99cfa93b29668f30 HTTP/1.0\nHost: picobrew.com\nConnection: close\n\n"
)
WIFI_MIXED_REQUEST = (
    b"GET /API/zymaticFirmwareCheck?machine=500000000000&ver=1&maj=1&min=14 HTTP/1.0\r\n"
    b"Host: picobrew.com\nConnection: close\n\n"
)


def feed(chunks: list[bytes]) -> bytes:
    normalizer = HeadNormalizer()
    return b"".join(normalizer.feed(chunk) for chunk in chunks)


@pytest.mark.parametrize("size", [1, 2, 3, 7, 1000])
def test_bare_lf_head_becomes_crlf_across_chunk_boundaries(size):
    head = b"GET / HTTP/1.0\nHost: a\r\nX: b\n\n"
    chunks = [head[i : i + size] for i in range(0, len(head), size)]
    assert feed(chunks) == b"GET / HTTP/1.0\r\nHost: a\r\nX: b\r\n\r\n"


def test_crlf_requests_and_bodies_pass_through_unchanged():
    request = b"POST /upload HTTP/1.1\r\nContent-Length: 6\r\n\r\na\nb\r\nc"
    assert feed([request[:20], request[20:40], request[40:]]) == request
    assert feed([b"GET / HTTP/1.0\n\nbody\n", b"more\n"]) == b"GET / HTTP/1.0\r\n\r\nbody\nmore\n"


def test_install_parses_every_request_on_a_keep_alive_connection():
    install()
    self_test()  # two pipelined bare-LF requests on one connection


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def send(port: int, request: bytes) -> bytes:
    with socket.create_connection(("127.0.0.1", port), timeout=10) as sock:
        sock.sendall(request)
        response = b""
        while chunk := sock.recv(4096):
            response += chunk
    return response


@pytest.fixture(scope="module")
def gunicorn_port(tmp_path_factory):
    # Start through the installed command from an unrelated directory, as a PyPI user would.
    workdir = tmp_path_factory.mktemp("cwd")
    data_dir = tmp_path_factory.mktemp("data")
    port = free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "picobrew_server.cli", "--host", "127.0.0.1", "--port", str(port)]
        + ["--workers", "1", "--data-dir", str(data_dir)],
        cwd=workdir,
        env={**os.environ, "GUNICORN_CMD_ARGS": "--http-parser python"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail(f"gunicorn did not start: {process.stderr.read().decode() if process.stderr else ''}")
                time.sleep(0.1)
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.parametrize(("request_bytes", "payload"), [(FIRMWARE_REQUEST, b"#T#"), (WIFI_MIXED_REQUEST, b"#F#")])
def test_gunicorn_answers_firmware_requests(gunicorn_port, request_bytes, payload):
    response = send(gunicorn_port, request_bytes)
    assert response.startswith(b"HTTP/1.0 200 OK\r\n")
    assert response.endswith(b"\r\n\r\n" + payload)


def test_repository_config_reexports_packaged_settings():
    settings = runpy.run_path(str(ROOT / "gunicorn.conf.py"))
    assert settings["wsgi_app"] == "picobrew_server:create_app()"
    assert settings["bind"] == "0.0.0.0:80"
