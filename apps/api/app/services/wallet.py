"""Loyalty Wallet pass payload (P4-004).

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

import hashlib
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import Client


_DEFAULT_TIER_BENEFITS = {
    "bronze": "1 pt = 0,10 € de réduction",
    "silver": "+5% sur tous les articles · 1 pt = 0,12 € de réduction",
    "gold": "+10% + accès prévente · 1 pt = 0,15 € de réduction",
}

_TIER_COLOR = {
    "bronze": "#B87333",
    "silver": "#C0C0C0",
    "gold": "#D4AF37",
}


@dataclass
class WalletPassPayload:
    """Backend-agnostic representation of the loyalty card.

    The ``apple`` and ``google`` blocks contain everything needed to
    sign + ship the real assets — they're filled in regardless of cert
    availability so the previewer can render the card visually."""

    client_id: str
    serial_number: str        # stable id derived from client.id
    holder_name: str
    membership_number: str    # human-readable card number
    tier: str
    points: int
    benefit_text: str
    primary_color: str
    issued_at: str
    qr_payload: str           # what the QR encodes — usually a URL
    apple: dict = field(default_factory=dict)
    google: dict = field(default_factory=dict)


def _membership_number(client_id: uuid.UUID) -> str:
    """Stable, short membership number (10 hex chars from a sha1)."""
    digest = hashlib.sha1(str(client_id).encode("utf-8")).hexdigest()
    return f"VTZ-{digest[:10].upper()}"


def _qr_payload(client_id: uuid.UUID) -> str:
    base = os.getenv("PUBLIC_SITE_URL", "https://vintiz.fr").rstrip("/")
    return f"{base}/account/data?membership={_membership_number(client_id)}"


def _apple_block(client: Client, points: int, tier: str) -> dict:
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
                {"key": "tier", "label": "Statut", "value": tier.title()},
                {
                    "key": "holder",
                    "label": "Titulaire",
                    "value": f"{client.first_name} {client.last_name}".strip(),
                },
            ],
            "auxiliaryFields": [{
                "key": "card",
                "label": "N° carte",
                "value": _membership_number(client.id),
            }],
        },
        "barcodes": [{
            "format": "PKBarcodeFormatQR",
            "message": _qr_payload(client.id),
            "messageEncoding": "iso-8859-1",
        }],
    }


def _google_block(client: Client, points: int, tier: str) -> dict:
    issuer_id = os.getenv("WALLET_GOOGLE_ISSUER_ID", "0000000000000000000")
    class_suffix = os.getenv("WALLET_GOOGLE_CLASS_SUFFIX", "vintiz_loyalty")
    class_id = f"{issuer_id}.{class_suffix}"
    object_id = f"{class_id}.{client.id}"
    return {
        "id": object_id,
        "classId": class_id,
        "state": "ACTIVE",
        "accountName": f"{client.first_name} {client.last_name}".strip(),
        "accountId": _membership_number(client.id),
        "loyaltyPoints": {
            "balance": {"int": points},
            "label": "Points",
        },
        "barcode": {
            "type": "QR_CODE",
            "value": _qr_payload(client.id),
        },
        "textModulesData": [{
            "header": "Statut",
            "body": tier.title(),
            "id": "tier",
        }],
    }


async def build_pass_for_client(
    db: AsyncSession, client_id: uuid.UUID
) -> WalletPassPayload | None:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        return None
    points = client.loyalty_account.points if client.loyalty_account else 0
    tier = (client.loyalty_account.tier if client.loyalty_account else "bronze").lower()
    benefit = _DEFAULT_TIER_BENEFITS.get(tier, _DEFAULT_TIER_BENEFITS["bronze"])

    return WalletPassPayload(
        client_id=str(client.id),
        serial_number=str(client.id),
        holder_name=f"{client.first_name} {client.last_name}".strip(),
        membership_number=_membership_number(client.id),
        tier=tier,
        points=points,
        benefit_text=benefit,
        primary_color=_TIER_COLOR.get(tier, _TIER_COLOR["bronze"]),
        issued_at=datetime.now(timezone.utc).isoformat(),
        qr_payload=_qr_payload(client.id),
        apple=_apple_block(client, points, tier),
        google=_google_block(client, points, tier),
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
