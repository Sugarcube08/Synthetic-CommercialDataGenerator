import uuid
from datetime import date, datetime
from typing import Any
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    customer_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(20))
    address_line1: Mapped[str | None] = mapped_column(String(300))
    address_line2: Mapped[str | None] = mapped_column(String(300))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(3), nullable=False, default="IND", server_default="IND")

    business_type: Mapped[str | None] = mapped_column(String(50))
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    credit_limit: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    behavioral_profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    sales: Mapped[list["SalesRecord"]] = relationship("SalesRecord", back_populates="customer")
    payments: Mapped[list["PaymentRecord"]] = relationship("PaymentRecord", back_populates="customer")
    returns: Mapped[list["ReturnRecord"]] = relationship("ReturnRecord", back_populates="customer")

    __table_args__ = (
        Index("idx_customers_code", "customer_code"),
        Index("idx_customers_active", "is_active"),
        Index("idx_customers_city", "city"),
        Index("idx_customers_reg_date", "registration_date"),
        Index("idx_customers_profile", "behavioral_profile", postgresql_using="gin"),
    )


class SalesRecord(Base):
    __tablename__ = "raw_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)

    product_category: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    gross_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    discount_pct: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0.0, server_default="0")
    discount_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    taxable_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=18.0, server_default="18.00")
    cgst_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    sgst_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    igst_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    total_tax: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    invoice_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)

    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30, server_default="30")
    amount_paid: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False, default=0.0, server_default="0")
    balance_due: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unpaid",
        server_default="unpaid",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    # Relationships
    customer: Mapped[Customer] = relationship("Customer", back_populates="sales")
    payments: Mapped[list["PaymentRecord"]] = relationship("PaymentRecord", back_populates="sale")
    returns: Mapped[list["ReturnRecord"]] = relationship("ReturnRecord", back_populates="sale")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="sales_quantity_check"),
        CheckConstraint("unit_price >= 0", name="sales_unit_price_check"),
        CheckConstraint("discount_pct >= 0 AND discount_pct <= 100", name="sales_discount_pct_check"),
        CheckConstraint("payment_status IN ('unpaid', 'partial', 'paid', 'overdue')", name="sales_payment_status_check"),
        Index("idx_sales_customer", "customer_id"),
        Index("idx_sales_invoice_num", "invoice_number"),
        Index("idx_sales_order_date", "order_date"),
        Index("idx_sales_due_date", "due_date"),
        Index("idx_sales_status", "payment_status"),
        Index("idx_sales_category", "product_category"),
    )


class PaymentRecord(Base):
    __tablename__ = "raw_payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_sales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    payment_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    payment_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    payment_mode: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="bank_transfer",
        server_default="bank_transfer",
    )
    reference_number: Mapped[str | None] = mapped_column(String(50))
    remarks: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    # Relationships
    customer: Mapped[Customer] = relationship("Customer", back_populates="payments")
    sale: Mapped[SalesRecord] = relationship("SalesRecord", back_populates="payments")

    __table_args__ = (
        CheckConstraint("payment_amount > 0", name="payments_amount_check"),
        CheckConstraint(
            "payment_mode IN ('bank_transfer', 'cheque', 'cash', 'upi', 'neft', 'rtgs', 'credit_note')",
            name="payments_mode_check",
        ),
        Index("idx_payments_customer", "customer_id"),
        Index("idx_payments_invoice", "invoice_id"),
        Index("idx_payments_date", "payment_date"),
        Index("idx_payments_mode", "payment_mode"),
    )


class ReturnRecord(Base):
    __tablename__ = "raw_returns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sale_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("raw_sales.id", ondelete="RESTRICT"),
        nullable=False,
    )
    return_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    return_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_reason: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity_returned: Mapped[int] = mapped_column(Integer, nullable=False)
    return_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    credit_note_number: Mapped[str | None] = mapped_column(String(30))
    credit_note_amount: Mapped[float | None] = mapped_column(Numeric(15, 2), default=0.0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    remarks: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    # Relationships
    customer: Mapped[Customer] = relationship("Customer", back_populates="returns")
    sale: Mapped[SalesRecord] = relationship("SalesRecord", back_populates="returns")

    __table_args__ = (
        CheckConstraint("quantity_returned > 0", name="returns_quantity_check"),
        CheckConstraint("return_value >= 0", name="returns_value_check"),
        CheckConstraint(
            "return_reason IN ('damaged_goods', 'delivery_issues', 'quality_defect', 'wrong_product', 'excess_inventory', 'customer_dissatisfaction', 'expired_product', 'pricing_dispute')",
            name="returns_reason_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'credited')",
            name="returns_status_check",
        ),
        Index("idx_returns_customer", "customer_id"),
        Index("idx_returns_sale", "sale_id"),
        Index("idx_returns_date", "return_date"),
        Index("idx_returns_reason", "return_reason"),
        Index("idx_returns_status", "status"),
    )
