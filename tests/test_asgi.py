"""Exercise HTTP requests through the production ASGI entry point."""

import asyncio
from urllib.parse import urlsplit

import pytest

from picobrew_server.asgi import create_app


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "SECRET_KEY": "test", "UPLOAD_FOLDER": str(tmp_path / "recipes")})


def request(app, url, method="GET", body=b"", headers=()):
    async def run():
        parts = urlsplit(url)
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": parts.path,
            "query_string": parts.query.encode(),
            "headers": [(b"host", b"localhost"), (b"content-length", str(len(body)).encode()), *headers],
            "server": ("localhost", 80),
            "client": ("127.0.0.1", 12345),
        }
        messages = []

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            messages.append(message)

        await asyncio.wait_for(app(scope, receive, send), timeout=5)
        start = messages[0]
        content = b"".join(message.get("body", b"") for message in messages[1:])
        return start["status"], dict(start["headers"]), content

    return asyncio.run(run())


@pytest.mark.parametrize(
    ("url", "status", "content"),
    [
        ("/", 200, b"Import your first recipe"),
        ("/API/zymaticFirmwareCheck?machine=500000000000&ver=1&maj=1&min=14", 200, b"#F#"),
        ("/missing", 404, b"404"),
        ("/static/img/grain.svg", 200, b"<svg"),
    ],
)
def test_http_routes(app, url, status, content):
    actual_status, _, body = request(app, url)
    assert actual_status == status
    assert content in body


def test_upload_body_redirect_and_session_cookie(app):
    body = (
        b'--boundary\r\nContent-Disposition: form-data; name="recipes"; filename="notes.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\nnot a recipe\r\n--boundary--\r\n"
    )
    status, headers, _ = request(
        app,
        "/upload",
        method="POST",
        body=body,
        headers=[(b"content-type", b"multipart/form-data; boundary=boundary")],
    )
    assert status == 302
    assert headers[b"location"].endswith(b"/import")
    cookie = headers[b"set-cookie"].split(b";", 1)[0]
    status, _, page = request(app, "/import", headers=[(b"cookie", cookie)])
    assert status == 200
    assert b"notes.txt: choose a BeerXML file" in page
