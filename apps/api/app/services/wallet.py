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
