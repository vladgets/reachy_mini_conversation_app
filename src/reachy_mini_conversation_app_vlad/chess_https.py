"""Standalone HTTPS server for the Reachy Chess Advisor browser extension.

Runs on port 7861 alongside the main app. Serves HTTPS so Chrome's MV3
extensions can connect (plain HTTP to private IPs is blocked by Chrome CSP).

On first start it generates a self-signed cert stored in the instance dir.
The cert is exposed at GET /chess/cert so the user can download and trust it
in macOS Keychain once — after that the extension connects permanently.
"""

import datetime
import logging
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from reachy_mini_conversation_app_vlad import chess_state

logger = logging.getLogger(__name__)

HTTPS_PORT = 7861

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _generate_cert(cert_dir: Path) -> tuple[Path, Path]:
    cert_path = cert_dir / "chess_cert.pem"
    key_path  = cert_dir / "chess_key.pem"
    if cert_path.exists() and key_path.exists():
        return cert_path, key_path

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "reachy-mini.local")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("reachy-mini.local"),
                x509.DNSName("localhost"),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    logger.info("chess_https: generated self-signed cert at %s", cert_path)
    return cert_path, key_path


def start(instance_path: Path) -> None:
    cert_dir = instance_path / "chess_cert"
    try:
        cert_path, key_path = _generate_cert(cert_dir)
    except Exception as e:
        logger.warning("chess_https: cert generation failed (%s) — HTTPS server not started", e)
        return

    app = FastAPI()

    @app.options("/chess")
    async def preflight() -> Response:
        return Response(headers=_CORS_HEADERS)

    @app.post("/chess")
    async def receive(request: Request) -> JSONResponse:
        chess_state.update(await request.json())
        return JSONResponse({"ok": True}, headers=_CORS_HEADERS)

    @app.get("/chess/state")
    async def state() -> JSONResponse:
        return JSONResponse(chess_state.get())

    @app.get("/chess/cert")
    async def download_cert() -> FileResponse:
        return FileResponse(cert_path, filename="reachy_chess.pem",
                            media_type="application/x-pem-file")

    def _run() -> None:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=HTTPS_PORT,
            ssl_certfile=str(cert_path),
            ssl_keyfile=str(key_path),
            log_level="warning",
        )

    threading.Thread(target=_run, daemon=True, name="chess-https").start()
    logger.info("chess_https: HTTPS server started on port %d", HTTPS_PORT)
