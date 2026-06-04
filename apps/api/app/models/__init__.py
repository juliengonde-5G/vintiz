from app.models.base import Base
from app.models.user import User
from app.models.product import Product, ProductPhoto, Category, PriceGrid
from app.models.inventory import Supplier, Order, OrderItem
from app.models.pos import Transaction, TransactionItem, Payment, CashDrawer, ZReport, Receipt
from app.models.client import (
    AvoirTransaction,
    AvoirTxType,
    Client,
    Consent,
    ConsentPurpose,
    LoyaltyAccount,
    LoyaltyTransaction,
)
from app.models.store import (
    AIRecommendation,
    FurnitureItem,
    StoreArrangement,
    StoreZone,
    TrendAnalysis,
    ZoneProduct,
    ZoneTag,
)
from app.models.reporting import DailyReport, CommercialAction, ActionResult
from app.models.audit import AuditLog, Settings
from app.models.batch import IntakeBatch, IntakeSource
from app.models.brand_tier import BrandTier, BrandTierLevel
from app.models.merchandising import WindowDisplayProposal
from app.models.visibility import (
    GoogleReview,
    SEOSnapshot,
    SocialMention,
    SocialPlatform,
    SocialPost,
    SocialPostCategory,
)
from app.models.events import EventLog, EventSource, EventType
from app.models.product_location import LocationMoveType, ProductLocationEvent
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.ai_task import AITask
from app.models.newsletter import NewsletterSubscriber
from app.models.coupon import Coupon, CouponDiscountType, CouponSource
from app.models.offer import Offer, OfferType
from app.models.weekly_task import WeeklyTask, WeeklyTaskKind, WeeklyTaskStatus
from app.models.window_decor import WindowDecor
from app.models.local_calendar import (
    CahierDayArchive,
    CommercialOperation,
    LocalEvent,
)
from app.models.auth import MagicLinkToken
from app.models.receipt_template import ReceiptKind, ReceiptTemplate
from app.models.communications import (
    CommunicationLog,
    MessageChannel,
    MessageTemplate,
)
from app.models.payment_attempt import PaymentAttempt, PaymentAttemptStatus
from app.models.cash_movement import (
    CashMovement,
    CashMovementDirection,
    CashMovementReason,
)
from app.models.sumup_terminal import SumUpTerminal, SumUpTerminalStatus
from app.models.accounting import (
    AccountingConfig,
    AccountingExport,
    AccountingExportLine,
    ExportStatus,
)
from app.models.database_backup import DatabaseBackup, DatabaseBackupConfig
from app.models.permanent_item import PermanentItem
from app.models.capsule import MonthlyCapsule

__all__ = [
    "Base",
    "User",
    "Product", "ProductPhoto", "Category", "PriceGrid",
    "Supplier", "Order", "OrderItem",
    "Transaction", "TransactionItem", "Payment", "CashDrawer", "ZReport", "Receipt",
    "Client", "LoyaltyAccount", "LoyaltyTransaction",
    "AvoirTransaction", "AvoirTxType",
    "Consent", "ConsentPurpose",
    "StoreZone", "ZoneProduct", "TrendAnalysis", "StoreArrangement", "AIRecommendation",
    "FurnitureItem", "ZoneTag",
    "DailyReport", "CommercialAction", "ActionResult",
    "AuditLog", "Settings",
    "EventLog", "EventSource", "EventType",
    "LocationMoveType", "ProductLocationEvent",
    "IntakeBatch", "IntakeSource",
    "BrandTier", "BrandTierLevel",
    "WindowDisplayProposal",
    "SEOSnapshot", "SocialPost", "SocialPostCategory", "SocialPlatform",
    "SocialMention", "GoogleReview",
    "ProductEmbedding", "CustomerTasteProfile", "EMBEDDING_DIM",
    "AITask",
    "NewsletterSubscriber",
    "Coupon", "CouponDiscountType", "CouponSource",
    "Offer", "OfferType",
    "WeeklyTask", "WeeklyTaskKind", "WeeklyTaskStatus",
    "WindowDecor",
    "LocalEvent", "CommercialOperation", "CahierDayArchive",
    "MagicLinkToken",
    "ReceiptKind", "ReceiptTemplate",
    "CommunicationLog", "MessageChannel", "MessageTemplate",
    "PaymentAttempt", "PaymentAttemptStatus",
    "CashMovement", "CashMovementDirection", "CashMovementReason",
    "SumUpTerminal", "SumUpTerminalStatus",
    "AccountingConfig", "AccountingExport", "AccountingExportLine", "ExportStatus",
    "DatabaseBackup", "DatabaseBackupConfig",
    "PermanentItem",
    "MonthlyCapsule",
]
