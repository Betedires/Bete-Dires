"""
payments.py — Payment & Escrow Gateway Integration Stub
Bete Dires (ቤተ ድረስ) Marketplace

Architecture Placeholder for Ethiopian Payment Gateways:
- Telebirr (Ethio Telecom API)
- CBE Birr (Commercial Bank of Ethiopia)
- Cash on Delivery (Manual / In-Person)

This module provides the clean interface and stub classes ready to connect
when online payments and escrow are activated. No live payments are processed yet.
"""

import enum
from typing import Optional, Dict, Any
from datetime import datetime

class PaymentProvider(str, enum.Enum):
    TELEBIRR = "telebirr"
    CBE_BIRR = "cbe_birr"
    CASH_ON_DELIVERY = "cash_on_delivery"

class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    ESCROW_HOLD = "escrow_hold"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

class EscrowTransaction:
    """Represents an escrow transaction holding buyer funds until item inspection."""
    def __init__(
        self,
        transaction_id: str,
        item_id: int,
        buyer_id: int,
        seller_id: int,
        amount_etb: float,
        provider: PaymentProvider,
        status: PaymentStatus = PaymentStatus.PENDING,
        created_at: Optional[datetime] = None
    ):
        self.transaction_id = transaction_id
        self.item_id = item_id
        self.buyer_id = buyer_id
        self.seller_id = seller_id
        self.amount_etb = amount_etb
        self.provider = provider
        self.status = status
        self.created_at = created_at or datetime.utcnow()

class PaymentGateway:
    """
    Unified payment gateway interface for Bete Dires Marketplace.
    Implementations for Telebirr and CBE Birr plug in here.
    """

    @classmethod
    async def create_checkout_session(
        cls,
        item_id: int,
        buyer_user_id: int,
        amount_etb: float,
        provider: PaymentProvider,
        return_url: str
    ) -> Dict[str, Any]:
        """
        Initiates a payment request with Telebirr or CBE Birr.
        Returns checkout URL / payment prompt details.
        """
        # PLUG-IN POINT: When activating live payments, generate Telebirr / CBE payment QR/USSD link here
        return {
            "status": "placeholder",
            "message": f"Payments for {provider.value} are not yet active on Bete Dires.",
            "item_id": item_id,
            "amount_etb": amount_etb,
            "provider": provider.value,
            "is_escrow_supported": True
        }

    @classmethod
    async def verify_payment_callback(
        cls,
        provider: PaymentProvider,
        callback_payload: Dict[str, Any],
        signature: str
    ) -> bool:
        """
        Verifies asynchronous webhook callbacks from Telebirr / CBE Birr servers.
        """
        # PLUG-IN POINT: Validate HMAC/RSA signature from provider
        return False

    @classmethod
    async def release_escrow_to_seller(cls, transaction_id: str) -> bool:
        """
        Releases held escrow funds to the seller after the buyer confirms item receipt.
        """
        # PLUG-IN POINT: Call provider payout / escrow release API
        return False

    @classmethod
    async def refund_buyer(cls, transaction_id: str, reason: str) -> bool:
        """
        Refunds held escrow funds back to the buyer if item was rejected or not delivered.
        """
        # PLUG-IN POINT: Call provider refund API
        return False
