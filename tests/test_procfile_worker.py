"""The production worker, as configured in the Procfile, must serve two things
behind Elastic Beanstalk's nginx:

* requests with a body, which nginx forwards with a bare `Connection: upgrade`
  header on every request (its default proxy config sets it unconditionally);
* WebSocket upgrades for Socket.IO.

These run a real gunicorn with the Procfile's worker settings, so they need
the packages in requirements.txt installed in the current interpreter.
"""
import json
import os
import pathlib
import shlex
import socket
import subprocess
import sys
import time

import jwt
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRET_KEY = "procfile-test"
GUNICORN = pathlib.Path(sys.executable).with_name("gunicorn")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _procfile_args(port):
    web = next(line for line in (ROOT / "Procfile").read_text().splitlines() if line.startswith("web:"))
    args = shlex.split(web.split(":", 1)[1])
    bind = args.index("--bind")
    args[bind + 1] = f"127.0.0.1:{port}"
    return args


@pytest.fixture(scope="module")
def gunicorn_port():
    if not GUNICORN.exists():
        pytest.skip("gunicorn is not installed next to this interpreter")
    port = _free_port()
    args = _procfile_args(port)
    args[0] = str(GUNICORN)
    env = dict(
        os.environ,
        DATABASE_ENGINE="postgres",
        DATABASE_URL="postgresql://unset",
        SECRET_KEY=SECRET_KEY,
        FLASK_ENV="development",
    )
    process = subprocess.Popen(args, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                socket.create_connection(("127.0.0.1", port), timeout=1).close()
                break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode())
                time.sleep(0.2)
        else:
            raise RuntimeError("gunicorn did not start listening")
        yield port
    finally:
        process.terminate()
        process.wait(timeout=10)


def _raw_request(port, request, timeout=5):
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(request)
        try:
            return sock.recv(4096)
        except socket.timeout:
            return None


def test_json_body_is_read_when_nginx_sends_connection_upgrade(gunicorn_port):
    # Authenticated, so the handler gets as far as parsing the JSON body. What
    # it does after that (here: talk to AWS) is not the point; answering is.
    token = jwt.encode({"id": "probe@example.com"}, SECRET_KEY, algorithm="HS256")
    body = json.dumps({"fileKey": "probe.txt", "fileType": "text/plain"}).encode()
    request = (
        b"POST /api/v2/images/presigned_url/ HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Connection: upgrade\r\n"
        b"Authorization: Bearer " + token.encode() + b"\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"\r\n" + body
    )
    response = _raw_request(gunicorn_port, request)
    assert response is not None, "no response within 5s: the worker never finished reading the body"
    assert response.startswith(b"HTTP/1.1 "), response[:120]
    assert not response.startswith(b"HTTP/1.1 401"), "token was rejected, so the body was never read"


def test_websocket_upgrade_is_accepted(gunicorn_port):
    request = (
        b"GET /socket.io/?EIO=4&transport=websocket HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Origin: https://www.umichkisa.com\r\n"
        b"Connection: upgrade\r\n"
        b"Upgrade: websocket\r\n"
        b"Sec-WebSocket-Version: 13\r\n"
        b"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
        b"\r\n"
    )
    response = _raw_request(gunicorn_port, request)
    assert response is not None, "no response to the WebSocket handshake within 5s"
    assert response.startswith(b"HTTP/1.1 101"), response[:120]
