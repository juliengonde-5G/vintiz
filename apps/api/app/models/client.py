import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class LoyaltyTxType(str, enum.Enum):
    earn = "earn"
    redeem = "redeem"
    adjust = "adjust"


class AvoirTxType(str, enum.Enum):
    credit = "credit"  # Issued from a refund — increases client balance
    debit = "debit"    # Spent at checkout — decreases client balance
    adjust = "adjust"  # Manual adjustment by manager


class ConsentPurpose(str, enum.Enum):
    """RGPD consent buckets tracked in the Consent ledger."""

    email_marketing = "email_marketing"
    sms_marketing = "sms_marketing"
    profiling = "profiling"        # Personal Shopper / AI recommendations
    trend_alerts = "trend_alerts"  # Email push when a trending product matches taste profile
    data_sharing = "data_sharing"  # Future B2B sharing — kept for forward compat


class Client(Base):
    __tablename__ = "clients"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_optin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Store credit (avoir) balance — incremented on refunds with method "avoir",
    # decremented when used at checkout. AvoirTransaction holds the audit trail.
    avoir_credit: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False, default=0
    )
    # RGPD soft-delete: set when the client requests erasure. A daily cron
    # hard-deletes rows whose timestamp is older than 30 days.
    deletion_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # RFM segmentation tag (P4-007). Recomputed monthly. Values:
    # champion / loyal / new / promising / at_risk / cant_lose / hibernating /
    # lost / unknown.
    rfm_segment: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Flag for seed / demo data (witness clients used to validate the
    # Personal Shopper flow). Pre-opening real clients keep the default
    # ``False`` and survive ``scripts/purge_test_data.py``.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Date of birth — drives the anniversary email cron (P4-008). Optional;
    # we ask for it on the onboarding form but never block account creation.
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Loyalty subscription metadata (PR1). subscribed_at = enrollment date,
    # expires_at = subscribed_at + 24mo (rolling on activity), mode records
    # which of {free, paid, first_purchase} was applied.
    loyalty_subscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    loyalty_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    loyalty_subscription_mode: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Last time a trend-alert email was sent — used by the cron's
    # frequency cap (1 alert / 7 days max). Nullable until the first send.
    last_trend_alert_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Declarative qualification — Personal Shopper 360 V1 onboarding "layer 1"
    # (base obligatoire). Collected on the espace-client onboarding wizard and
    # used to seed the taste profile, filter the visual cold-start candidates,
    # and (later) target communications. Additive + nullable (migration 0051):
    # existing rows stay NULL. The *computed* qualification signals
    # (season_bias / price_ceiling / price_sensitivity / trend_affinity) land
    # in V2 via the customer_qualification service — intentionally not here.
    gender_profile: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # femme | homme | mixte
    age_band: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # <25 | 25-34 | 35-44 | 45-54 | 55+

    # Computed qualification signals — Personal Shopper 360 V2. Refreshed by
    # ``customer_qualification`` (per transaction + nightly batch) from the last
    # 15 sale transactions, gifts excluded. Additive + nullable (migration
    # 0052); NULL = not enough history yet. Enrich the reco + the appro brief
    # without touching the embedding engine.
    season_bias: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # winter | summer | all
    price_ceiling_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_sensitivity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1
    trend_affinity: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0..1

    loyalty_account: Mapped["LoyaltyAccount | None"] = relationship(
        "LoyaltyAccount", back_populates="client", uselist=False, lazy="selectin"
    )


class LoyaltyAccount(Base):
    __tablename__ = "loyalty_accounts"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), unique=True, nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Human-readable card number, format V###### (V + 6 digits). Unique.
    membership_number: Mapped[str] = mapped_column(
        String(8), unique=True, nullable=False
    )

    client: Mapped["Client"] = relationship(
        "Client", back_populates="loyalty_account", lazy="selectin"
    )
    transactions: Mapped[list["LoyaltyTransaction"]] = relationship(
        "LoyaltyTransaction", back_populates="account", lazy="selectin"
    )


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loyalty_accounts.id"), nullable=False
    )
    tx_type: Mapped[LoyaltyTxType] = mapped_column(
        Enum(LoyaltyTxType, name="loyalty_tx_type"), nullable=False
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    account: Mapped["LoyaltyAccount"] = relationship(
        "LoyaltyAccount", back_populates="transactions", lazy="selectin"
    )


class Consent(Base):
    """Append-only ledger of RGPD consent decisions per client × purpose.

    Each row captures a single grant/revoke event with metadata sufficient
    for an audit (who recorded it, on which policy version, from where).
    The current consent for a purpose is the most recent row's ``granted``.
    """

    __tablename__ = "consents"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    purpose: Mapped[ConsentPurpose] = mapped_column(
        Enum(ConsentPurpose, name="consent_purpose"), nullable=False
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # e.g. "site_signup", "pos", "admin", "import"
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class AvoirTransaction(Base):
    """Append-only ledger of avoir credits and debits.

    Sums of (credit - debit) by client_id reproduce Client.avoir_credit and
    serve as the audit trail required by NF525 for refunds settled in
    store credit.
    """

    __tablename__ = "avoir_transactions"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )
    tx_type: Mapped[AvoirTxType] = mapped_column(
        Enum(AvoirTxType, name="avoir_tx_type"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
