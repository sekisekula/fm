from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON, DateTime, Boolean, CHAR, Numeric, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    payments = relationship("UserPayment", back_populates="user")
    settlements_as_payer = relationship("Settlement", foreign_keys="Settlement.payer_user_id", back_populates="payer")
    settlements_as_debtor = relationship("Settlement", foreign_keys="Settlement.debtor_user_id", back_populates="debtor")

class ProductShare(Base):
    __tablename__ = "product_shares"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, unique=True, index=True)
    shares = Column(JSON)

class Share(Base):
    __tablename__ = "shares"

    share_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.product_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    share = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Receipt(Base):
    __tablename__ = "receipts"

    receipt_id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.store_id"), nullable=False)
    receipt_number = Column(String, nullable=False)
    date = Column(DateTime, nullable=False)
    time = Column(String, nullable=False)
    final_price = Column(Numeric(10, 2), nullable=False)
    total_discounts = Column(Numeric(10, 2))
    payment_name = Column(String, ForeignKey("user_payments.payment_name"), nullable=False)
    counted = Column(Boolean, default=False)
    settled = Column(Boolean, default=False)
    not_our_receipt = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    currency = Column(CHAR(3), nullable=False, default='PLN')
    store = relationship("Store", back_populates="receipts")

class Product(Base):
    __tablename__ = "products"

    product_id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.receipt_id"), nullable=True)
    manual_expense_id = Column(Integer, ForeignKey("manual_expenses.manual_expense_id"), nullable=True)
    product_name = Column(String, nullable=False)
    quantity = Column(Numeric(10, 3), nullable=False)
    tax_type = Column(CHAR(1), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    unit_price_before = Column(Numeric(10, 2), nullable=False)
    total_price_before = Column(Numeric(10, 2), nullable=False)
    unit_discount = Column(Numeric(10, 2))
    total_discount = Column(Numeric(10, 2))
    unit_after_discount = Column(Numeric(10, 2))
    total_after_discount = Column(Numeric(10, 2), nullable=False)

class UserPayment(Base):
    __tablename__ = "user_payments"

    user_payment_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    payment_name = Column(String, nullable=False, unique=True)
    user = relationship("User", back_populates="payments")

class IgnoredPaymentName(Base):
    __tablename__ = "ignored_payment_names"

    id = Column(Integer, primary_key=True, index=True)
    payment_name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Settlement(Base):
    __tablename__ = "settlements"

    settlement_id = Column(Integer, primary_key=True, index=True)
    payer_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    debtor_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payer = relationship("User", foreign_keys=[payer_user_id], back_populates="settlements_as_payer")
    debtor = relationship("User", foreign_keys=[debtor_user_id], back_populates="settlements_as_debtor")

class Store(Base):
    __tablename__ = "stores"

    store_id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String, nullable=False)
    store_city = Column(String)
    store_address = Column(String, nullable=False)
    postal_code = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    receipts = relationship("Receipt", back_populates="store")


class ManualExpense(Base):
    __tablename__ = "manual_expenses"

    manual_expense_id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, nullable=False)
    description = Column(Text)
    total_cost = Column(Numeric(10, 2), nullable=False)
    payer_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    counted = Column(Boolean, default=True)
    settled = Column(Boolean, default=False)
    category = Column(String(255), default='Other')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    payer = relationship("User", foreign_keys=[payer_user_id])


class StaticShare(Base):
    __tablename__ = "static_shares"
    
    share_id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String(255), unique=True, nullable=False)
    share = Column(Numeric(5, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SettlementItem(Base):
    __tablename__ = "settlement_items"

    settlement_item_id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(Integer, ForeignKey("settlements.settlement_id"), nullable=False)
    receipt_id = Column(Integer, ForeignKey("receipts.receipt_id"), nullable=True)
    manual_expense_id = Column(Integer, ForeignKey("manual_expenses.manual_expense_id"), nullable=True)

class StaticShareHistory(Base):
    __tablename__ = "static_shares_history"

    history_id = Column(Integer, primary_key=True, index=True)
    share_id = Column(Integer, ForeignKey("static_shares.share_id"), nullable=False)
    old_share = Column(Numeric(5, 2))
    new_share = Column(Numeric(5, 2), nullable=False)
    changed_by = Column(String(255), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    change_reason = Column(Text)

class DatabaseBackup(Base):
    __tablename__ = "database_backups"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    size = Column(Integer, nullable=False)  # Size in bytes
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(100))
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
