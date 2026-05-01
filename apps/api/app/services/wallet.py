"""Loyalty Wallet pass payload (PR1 — single-tier, V###### card).

Apple Wallet (.pkpass) and Google Wallet both accept a JSON description
of the loyalty card. They differ in:

- **Schema**: Apple uses ``passTypeIdentifier`` + a ``storeCard`` block.
  Google uses a ``LoyaltyObject`` document under a ``classId``.
- **Signing**: Apple needs a p12 cert + WWDR cert and a SHA-1
  ``manifest.json`` ZIP. Google needs a Service Account JSON to sign a
  JWT.

Both signing flows depend on production secrets that are not part of
the development environment, so this service exposes the **payload**
in a backend-agnostic shape that the front (or a deploy-time signing
script) can transform into the actual ``.pkpass`` ZIP / signed JWT.

Settings honoured:
- ``WALLET_PASS_TYPE_IDENTIFIER``  (Apple, e.g. ``pass.fr.vintiz.loyalty``)
- ``WALLET_TEAM_IDENTIFIER``        (Apple)
- ``WALLET_GOOGLE_ISSUER_ID``       (Google)
- ``WALLET_GOOGLE_CLASS_SUFFIX``    (Google, default ``vintiz_loyalty``)
- ``PUBLIC_SITE_URL``               (used in QR code & web fallback)

When a setting is missing, the payload is still emitted with placeholder
values so the front can render a "preview" Wallet card; the manager UI
warns when the real signing keys aren't configured yet.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client


PRIMARY_COLOR = "#008678"  # Vintiz teal — single brand color now
BENEFIT_TEXT = "1 € = 1 pt · 100 pts = bon de 8 €"


@dataclass
class WalletPassPayload:
    """Backend-agnostic representation of the loyalty card."""

    client_id: str
    serial_number: str        # stable id derived from client.id
    holder_name: str
    membership_number: str    # human-readable card number (V######)
    points: int
    benefit_text: str
    primary_color: str
    issued_at: str
    qr_payload: str           # what the QR encodes — usually a URL
    apple: dict = field(default_factory=dict)
    google: dict = field(default_factory=dict)


def _qr_payload(membership_number: str) -> str:
    base = os.getenv("PUBLIC_SITE_URL", "https://vintiz.fr").rstrip("/")
    return f"{base}/account/login?membership={membership_number}"


def _apple_block(client: Client, points: int, membership_number: str) -> dict:
    pass_type_id = os.getenv("WALLET_PASS_TYPE_IDENTIFIER", "pass.fr.vintiz.loyalty")
    team_id = os.getenv("WALLET_TEAM_IDENTIFIER", "TEAMID0000")
    serial = str(client.id)
    return {
        "formatVersion": 1,
        "passTypeIdentifier": pass_type_id,
        "teamIdentifier": team_id,
        "organizationName": "Vintiz",
        "description": "Carte fidélité Vintiz",
        "serialNumber": serial,
        "logoText": "Vintiz",
        "foregroundColor": "rgb(255, 255, 255)",
        "backgroundColor": "rgb(0, 134, 120)",  # Vintiz teal
        "labelColor": "rgb(255, 197, 223)",      # Vintiz pink
        "storeCard": {
            "primaryFields": [{
                "key": "points",
                "label": "Points",
                "value": str(points),
            }],
            "secondaryFields": [
                {
                    "key": "holder",
                    "label": "Titulaire",
                    "value": f"{client.first_name} {client.last_name}".strip(),
                },
            ],
            "auxiliaryFields": [{
                "key": "card",
                "label": "N° carte",
                "value": membership_number,
            }],
        },
        "barcodes": [{
            "format": "PKBarcodeFormatQR",
            "message": _qr_payload(membership_number),
            "messageEncoding": "iso-8859-1",
        }],
    }


def _google_block(client: Client, points: int, membership_number: str) -> dict:
    issuer_id = os.getenv("WALLET_GOOGLE_ISSUER_ID", "0000000000000000000")
    class_suffix = os.getenv("WALLET_GOOGLE_CLASS_SUFFIX", "vintiz_loyalty")
    class_id = f"{issuer_id}.{class_suffix}"
    object_id = f"{class_id}.{client.id}"
    return {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE",
        "accountName": f"{client.first_name} {client.last_name}".strip(),
        "accountId": membership_number,
        "loyaltyPoints": {
            "balance": {"int": points},
            "label": "Points",
        },
        "barcode": {
            "type": "QR_CODE",
            "value": _qr_payload(membership_number),
        },
    }


async def build_pass_for_client(
    db: AsyncSession, client_id: uuid.UUID
) -> WalletPassPayload | None:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None or client.loyalty_account is None:
        return None
    points = client.loyalty_account.points or 0
    membership_number = client.loyalty_account.membership_number

    return WalletPassPayload(
        client_id=str(client.id),
        serial_number=str(client.id),
        holder_name=f"{client.first_name} {client.last_name}".strip(),
        membership_number=membership_number,
        points=points,
        benefit_text=BENEFIT_TEXT,
        primary_color=PRIMARY_COLOR,
        issued_at=datetime.now(timezone.utc).isoformat(),
        qr_payload=_qr_payload(membership_number),
        apple=_apple_block(client, points, membership_number),
        google=_google_block(client, points, membership_number),
    )


async def build_pass_by_email(
    db: AsyncSession, email: str
) -> WalletPassPayload | None:
    result = await db.execute(
        select(Client).where(Client.email == email.strip().lower())
    )
    client = result.scalar_one_or_none()
    if client is None:
        return None
    return await build_pass_for_client(db, client.id)


def payload_to_dict(payload: WalletPassPayload) -> dict:
    return asdict(payload)


# ---------------------------------------------------------------------------
# Apple Wallet — real .pkpass build (signed if certs configured)
# ---------------------------------------------------------------------------

_APPLE_TEAM_ID_PLACEHOLDER = "TEAMID0000"


def _apple_certs_configured() -> bool:
    """Real .pkpass needs the developer p12 + WWDR cert + a real teamId."""
    p12_path = os.getenv("WALLET_APPLE_P12_PATH", "").strip()
    wwdr_path = os.getenv("WALLET_APPLE_WWDR_PATH", "").strip()
    team = os.getenv("WALLET_TEAM_IDENTIFIER", "").strip()
    return bool(p12_path and wwdr_path and team and team != _APPLE_TEAM_ID_PLACEHOLDER)


def apple_wallet_available() -> bool:
    """Public alias — front-end checks before showing the .pkpass button."""
    return _apple_certs_configured()


def build_apple_pkpass(payload: WalletPassPayload) -> bytes | None:
    """Produce a signed ``.pkpass`` ZIP, or ``None`` when certs are missing.

    The ``.pkpass`` archive contains:
      - ``pass.json`` (the Apple block)
      - ``manifest.json`` (SHA-1 of every file in the archive)
      - ``signature``    (PKCS#7 signature of manifest.json with the p12 cert
                           chained to the WWDR intermediate)
      - ``icon.png``, ``icon@2x.png``, ``logo.png`` (visual assets)

    We rely on the project-level ``cryptography`` lib (transitive via PyJWT in
    other services) to produce the PKCS#7 detached signature. The icon assets
    fall back to a 1×1 transparent PNG when ``WALLET_PASS_ASSETS_DIR`` is unset
    so the archive is at least valid; in production the manager should provide
    a 29×29 / 58×58 / 87×87 logo set in that directory.
    """
    if not _apple_certs_configured():
        return None
    try:
        import hashlib
        import io
        import json as _json
        import zipfile
        from pathlib import Path

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography import x509  # noqa: F401 (used by load_pem_x509_certificate)
        try:
            # cryptography >= 41 ships PKCS7 signing under hazmat.primitives.serialization.pkcs7
            from cryptography.hazmat.primitives.serialization import pkcs7 as _pkcs7
        except ImportError:  # pragma: no cover - only triggers on outdated installs
            return None

        p12_path = Path(os.getenv("WALLET_APPLE_P12_PATH", "")).expanduser()
        p12_password = os.getenv("WALLET_APPLE_P12_PASSWORD", "").encode("utf-8") or None
        wwdr_path = Path(os.getenv("WALLET_APPLE_WWDR_PATH", "")).expanduser()
        if not (p12_path.is_file() and wwdr_path.is_file()):
            return None

        # 1) Load signing key + cert
        with p12_path.open("rb") as fh:
            private_key, signing_cert, _additional_certs = pkcs12.load_key_and_certificates(
                fh.read(), p12_password
            )
        if private_key is None or signing_cert is None:
            return None

        with wwdr_path.open("rb") as fh:
            wwdr_pem = fh.read()
        try:
            wwdr_cert = x509.load_pem_x509_certificate(wwdr_pem)
        except ValueError:
            wwdr_cert = x509.load_der_x509_certificate(wwdr_pem)

        # 2) Build pass.json
        pass_json = _json.dumps(payload.apple, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        # 3) Assets — load from WALLET_PASS_ASSETS_DIR if available, else fall back
        assets_dir = Path(os.getenv("WALLET_PASS_ASSETS_DIR", "")).expanduser()
        # 1×1 transparent PNG (good enough for a valid archive)
        _TRANSPARENT_PNG = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?"
            b"\x03\x00\x05\xfe\x02\xfe\xa3\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        def _asset(name: str) -> bytes:
            if assets_dir.is_dir():
                candidate = assets_dir / name
                if candidate.is_file():
                    return candidate.read_bytes()
            return _TRANSPARENT_PNG

        files: dict[str, bytes] = {
            "pass.json": pass_json,
            "icon.png": _asset("icon.png"),
            "icon@2x.png": _asset("icon@2x.png"),
            "logo.png": _asset("logo.png"),
        }

        # 4) Manifest: SHA-1 of each file, hex-encoded
        manifest = {name: hashlib.sha1(blob).hexdigest() for name, blob in files.items()}  # noqa: S324 — Apple spec
        manifest_bytes = _json.dumps(manifest, separators=(",", ":")).encode("utf-8")

        # 5) PKCS#7 detached signature of manifest.json
        # noqa: cryptography >= 41
        builder = _pkcs7.PKCS7SignatureBuilder().set_data(manifest_bytes).add_signer(
            signing_cert, private_key, hashes.SHA256()
        ).add_certificate(wwdr_cert)
        signature = builder.sign(
            serialization.Encoding.DER,
            options=[_pkcs7.PKCS7Options.DetachedSignature, _pkcs7.PKCS7Options.Binary],
        )

        # 6) Bundle the ZIP
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, blob in files.items():
                zf.writestr(name, blob)
            zf.writestr("manifest.json", manifest_bytes)
            zf.writestr("signature", signature)
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001 — never crash the request
        import logging
        logging.getLogger("vintiz.wallet").warning("apple_pkpass build failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Google Wallet — Save URL (signed JWT)
# ---------------------------------------------------------------------------


def _google_creds_configured() -> bool:
    sa_path = os.getenv("WALLET_GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    issuer = os.getenv("WALLET_GOOGLE_ISSUER_ID", "").strip()
    return bool(sa_path and issuer and issuer != "0000000000000000000")


def google_wallet_available() -> bool:
    """Public alias — front-end checks before showing the Google Wallet button."""
    return _google_creds_configured()


def build_google_save_url(payload: WalletPassPayload) -> str | None:
    """Return ``https://pay.google.com/gp/v/save/<JWT>`` or ``None``.

    The JWT is RS256-signed with the Service Account private key. We embed
    the LoyaltyObject inline so the user does not need an existing object on
    the issuer side.
    """
    if not _google_creds_configured():
        return None
    try:
        import json as _json
        import time
        from pathlib import Path

        try:
            import jwt as _jwt  # PyJWT
        except ImportError:
            return None

        sa_path = Path(os.getenv("WALLET_GOOGLE_SERVICE_ACCOUNT_JSON", "")).expanduser()
        if not sa_path.is_file():
            return None
        with sa_path.open("r", encoding="utf-8") as fh:
            sa = _json.load(fh)
        client_email = sa.get("client_email")
        private_key = sa.get("private_key")
        if not (client_email and private_key):
            return None

        now = int(time.time())
        body = {
            "iss": client_email,
            "aud": "google",
            "typ": "savetowallet",
            "iat": now,
            "payload": {"loyaltyObjects": [payload.google]},
        }
        token = _jwt.encode(body, private_key, algorithm="RS256")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return f"https://pay.google.com/gp/v/save/{token}"
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("vintiz.wallet").warning("google save_url build failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# QR fallback — always available, used when certs/credentials are missing
# ---------------------------------------------------------------------------


def build_qr_png(payload: WalletPassPayload) -> bytes | None:
    """Return a PNG of the QR code that encodes the membership URL."""
    try:
        import io
        import qrcode  # type: ignore[import-not-found]

        img = qrcode.make(payload.qr_payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger("vintiz.wallet").warning("qr png build failed: %s", exc)
        return None
