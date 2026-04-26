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
from app.models.store import StoreZone, ZoneProduct, TrendAnalysis, StoreArrangement, AIRecommendation
from app.models.reporting import DailyReport, CommercialAction, ActionResult
from app.models.audit import AuditLog, Settings
from app.models.batch import IntakeBatch, IntakeSource
from app.models.merchandising import WindowDisplayProposal
from app.models.events import EventLog, EventSource, EventType
from app.models.embeddings import (
    EMBEDDING_DIM,
    CustomerTasteProfile,
    ProductEmbedding,
)
from app.models.ai_task import AITask
from app.models.newsletter import NewsletterSubscriber

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
    "DailyReport", "CommercialAction", "ActionResult",
    "AuditLog", "Settings",
    "EventLog", "EventSource", "EventType",
    "IntakeBatch", "IntakeSource",
    "WindowDisplayProposal",
    "ProductEmbedding", "CustomerTasteProfile", "EMBEDDING_DIM",
    "AITask",
    "NewsletterSubscriber",
]
