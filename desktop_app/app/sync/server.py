from __future__ import annotations

import json
import secrets
import socket
import ssl
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from app.core.database import connect
from app.services.sync_service import SyncService
from app.sync.identity import ensure_server_identity
from app.sync.protocol import ENTITY_SET_VERSION, PROTOCOL_VERSION


MAX_REQUEST_BYTES = 2 * 1024 * 1024


class LocalSyncServer:
    """Opt-in HTTPS endpoint available only while the desktop app is open."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.requested_port = port
        self.httpd: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None
        self.pairing_code = ""
        self.pairing_expires_at = 0.0
        self.pairing_generation = 0
        self.certificate_path, self.private_key_path, self.fingerprint = (
            ensure_server_identity()
        )

    @property
    def is_running(self) -> bool:
        return self.httpd is not None

    @property
    def port(self) -> int:
        if not self.httpd:
            return self.requested_port
        return int(self.httpd.server_address[1])

    @property
    def url(self) -> str:
        return f"https://{_lan_address()}:{self.port}"

    def start(self) -> dict:
        if self.httpd:
            return self.pairing_details()
        handler = _handler_for(self)
        try:
            server = ThreadingHTTPServer((self.host, self.requested_port), handler)
        except OSError:
            server = ThreadingHTTPServer((self.host, 0), handler)
        server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.certificate_path, self.private_key_path)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        self.httpd = server
        self.regenerate_pairing_code()
        self.thread = threading.Thread(
            target=server.serve_forever,
            name="money-manager-local-sync",
            daemon=True,
        )
        self.thread.start()
        return self.pairing_details()

    def stop(self) -> None:
        server = self.httpd
        thread = self.thread
        self.httpd = None
        self.thread = None
        self.pairing_code = ""
        self.pairing_expires_at = 0.0
        if server:
            server.shutdown()
            server.server_close()
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def regenerate_pairing_code(self) -> str:
        self.pairing_code = f"{secrets.randbelow(1_000_000):06d}"
        self.pairing_expires_at = time.monotonic() + 600
        self.pairing_generation += 1
        return self.pairing_code

    def pairing_details(self) -> dict:
        if not self.httpd:
            raise RuntimeError("Phone sync is not running")
        return {
            "url": self.url,
            "code": self.pairing_code,
            "fingerprint": self.fingerprint,
            "protocol_version": PROTOCOL_VERSION,
            "entity_set_version": ENTITY_SET_VERSION,
            "expires_in_seconds": max(
                0, int(self.pairing_expires_at - time.monotonic())
            ),
        }

    def claim_pairing_code(self, value: str) -> bool:
        return bool(
            self.pairing_code
            and time.monotonic() < self.pairing_expires_at
            and secrets.compare_digest(self.pairing_code, str(value).strip())
        )

    def consume_pairing_code(self) -> None:
        self.regenerate_pairing_code()


def _handler_for(owner: LocalSyncServer):
    class SyncHandler(BaseHTTPRequestHandler):
        server_version = "MoneyManagerSync/1"

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/v1/hello":
                self._send(404, {"error": "Not found"})
                return
            with closing(connect()) as db:
                payload = SyncService(db).hello()
            payload["certificate_fingerprint"] = owner.fingerprint
            self._send(200, payload)

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = self._read_json()
                if self.path == "/v1/pair":
                    self._pair(body)
                    return
                if self.path == "/v1/sync":
                    self._sync(body)
                    return
                self._send(404, {"error": "Not found"})
            except ValueError as exc:
                self._send(400, {"error": str(exc)})
            except json.JSONDecodeError:
                self._send(400, {"error": "Request body must be valid JSON"})
            except Exception:
                self._send(500, {"error": "The desktop could not complete the request"})

        def _pair(self, body: dict) -> None:
            if not owner.claim_pairing_code(str(body.get("code", ""))):
                self._send(403, {"error": "Pairing code is incorrect or expired"})
                return
            with closing(connect()) as db:
                result = SyncService(db).pair_device(
                    str(body.get("device_id", "")),
                    str(body.get("display_name", "Android phone")),
                    owner.fingerprint,
                )
            owner.consume_pairing_code()
            result["certificate_fingerprint"] = owner.fingerprint
            self._send(200, result)

        def _sync(self, body: dict) -> None:
            device_id = str(body.get("device_id", ""))
            token = self._bearer_token()
            with closing(connect()) as db:
                service = SyncService(db)
                if not service.authenticate(device_id, token):
                    self._send(401, {"error": "Device authorization failed"})
                    return
                result = service.exchange(
                    device_id,
                    int(body.get("cursor", 0)),
                    body.get("commands") or [],
                    entity_set_version=body.get("entity_set_version"),
                )
            self._send(200, result)

        def _read_json(self) -> dict:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Invalid content length") from exc
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("Request body size is invalid")
            decoded: Any = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("Request body must be a JSON object")
            return decoded

        def _bearer_token(self) -> str:
            authorization = self.headers.get("Authorization", "")
            scheme, _, token = authorization.partition(" ")
            return token.strip() if scheme.lower() == "bearer" else ""

        def _send(self, status: int, payload: dict) -> None:
            encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args) -> None:
            return

    return SyncHandler


def _lan_address() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("1.1.1.1", 80))
        address = str(probe.getsockname()[0])
        if address and not address.startswith("127."):
            return address
    except OSError:
        pass
    finally:
        probe.close()
    try:
        addresses = socket.gethostbyname_ex(socket.gethostname())[2]
        return next(address for address in addresses if not address.startswith("127."))
    except (OSError, StopIteration):
        return "127.0.0.1"
