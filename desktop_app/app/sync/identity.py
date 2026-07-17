from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.paths import app_data_dir


def ensure_server_identity() -> tuple[Path, Path, str]:
    identity_dir = app_data_dir() / "sync"
    identity_dir.mkdir(parents=True, exist_ok=True)
    certificate_path = identity_dir / "desktop.crt"
    private_key_path = identity_dir / "desktop.key"
    if not certificate_path.exists() or not private_key_path.exists():
        _create_identity(certificate_path, private_key_path)
    certificate_bytes = certificate_path.read_bytes()
    certificate = x509.load_pem_x509_certificate(certificate_bytes)
    fingerprint = hashlib.sha256(
        certificate.public_bytes(serialization.Encoding.DER)
    ).hexdigest()
    return certificate_path, private_key_path, fingerprint


def _create_identity(certificate_path: Path, private_key_path: Path) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Money Manager Desktop")]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("Money Manager Desktop")]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    private_key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    certificate_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    try:
        private_key_path.chmod(0o600)
    except OSError:
        pass
