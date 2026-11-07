from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RFQRequestRecord(Base):
    __tablename__ = "rfq_requests"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    request_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        nullable=False,
    )

    customer_id: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
    )

    reason_codes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    quote_subtotal_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=12,
            scale=2,
        ),
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_response_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    model_latency_ms: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=12,
            scale=2,
        ),
        nullable=True,
    )

    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=18,
            scale=10,
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RFQLineRecord(Base):
    __tablename__ = "rfq_lines"

    __table_args__ = (
        UniqueConstraint(
            "rfq_id",
            "line_number",
            name="uq_rfq_lines_rfq_line_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    rfq_id: Mapped[int] = mapped_column(
        ForeignKey(
            "rfq_requests.id",
            ondelete="CASCADE",
        ),
        index=True,
        nullable=False,
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    product_query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=18,
            scale=4,
        ),
        nullable=True,
    )

    unit: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    extraction_issues: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    match_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    matched_sku: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    decision_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    decision_reason_codes: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
    )

    subtotal_eur: Mapped[Decimal | None] = mapped_column(
        Numeric(
            precision=12,
            scale=2,
        ),
        nullable=True,
    )
