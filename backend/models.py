from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from database import Base


class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    email = Column(String(120), nullable=True)
    total_orders = Column(Integer, default=0)
    last_order_date = Column(DateTime, nullable=True)
    city = Column(String(100), nullable=True)
    tags = Column(String(255), nullable=True)  # Comma-separated tags e.g. "VIP, wholesale, regular"
    birth_day = Column(Integer, nullable=True)  # 1-31
    birth_month = Column(Integer, nullable=True)  # 1-12
    is_active = Column(Boolean, default=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    custom_attributes = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class DiscountCode(Base):
    __tablename__ = "discount_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    discount_type = Column(String(20), default="PERCENT")  # PERCENT or FLAT
    discount_value = Column(Float, nullable=False)          # e.g. 15.0 (%) or 100.0 (₹)
    min_order_value = Column(Float, default=0.0)
    max_uses = Column(Integer, default=1000)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CartEvent(Base):
    __tablename__ = "cart_events"

    id = Column(Integer, primary_key=True, index=True)
    cart_token = Column(String(100), index=True, nullable=False)
    customer_phone = Column(String(20), index=True, nullable=False)
    cart_value = Column(Float, default=0.0)
    items = Column(JSON, default=list)
    extra_data = Column(JSON, default=dict)  # Arbitrary dynamic fields from ecom store (e.g. firstname, products_summary, address)
    status = Column(String(50), default="PENDING")  # PENDING, RECOVERED, EXPIRED
    authenticated_user = Column(String(50), nullable=True)  # User or API token owner who sent this webhook
    message_sent = Column(Boolean, default=False)
    message_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("source", "external_event_id", name="uq_webhook_events_source_external_event_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(50), nullable=False, default="store", index=True)  # 'store', 'meta', 'internal_sim'
    event_type = Column(String(50), nullable=False)
    external_event_id = Column(String(150), nullable=True, index=True)
    idempotency_key = Column(String(150), unique=True, index=True, nullable=False)
    hmac_validated = Column(Boolean, default=False, nullable=False)
    correlation_id = Column(String(64), nullable=True, index=True)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OptOut(Base):
    __tablename__ = "opt_outs"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    reason = Column(String(255), default="USER_REQUEST")  # e.g., 'STOP' reply
    created_at = Column(DateTime, default=datetime.utcnow)


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), index=True, nullable=False)
    source = Column(String(50), nullable=False, default="store_checkout")  # store_checkout, inbound_message, manual_import, csv_import
    status = Column(String(20), nullable=False, default="ACTIVE")          # ACTIVE, REVOKED
    proof_details = Column(Text, nullable=True)
    consent_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True)
    recipient_phone = Column(String(20), index=True, nullable=False)
    template_name = Column(String(100), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    language = Column(String(10), default="en")
    status = Column(String(50), default="QUEUED")  # QUEUED, SENT, DELIVERED, READ, FAILED
    sender_user = Column(String(50), nullable=True, default="System")  # User or API client who initiated message
    meta_message_id = Column(String(100), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    template_name = Column(String(100), nullable=False)
    language = Column(String(10), default="en")
    target_filter = Column(String(50), default="ALL")
    status = Column(String(50), default="DRAFT")
    total_recipients = Column(Integer, default=0)
    successful_sends = Column(Integer, default=0)
    failed_sends = Column(Integer, default=0)
    per_day_limit = Column(Integer, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    # WP8: Worker lease columns for distributed broadcast claiming
    claimed_by = Column(String(64), nullable=True)
    claimed_until = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="agent", nullable=False)
    is_2fa_enabled = Column(Boolean, default=False)
    totp_secret = Column(String(64), nullable=True)
    email_recovery_code = Column(String(10), nullable=True)
    email_recovery_code_expires = Column(DateTime, nullable=True)
    auth_version = Column(Integer, default=1, nullable=False)
    can_support_send = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        # Ignore legacy api_token fields if passed by old fixtures
        kwargs.pop("api_token", None)
        kwargs.pop("api_token_created_at", None)
        super().__init__(**kwargs)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    family_id = Column(String(64), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    rotated_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        is_rev = kwargs.pop("is_revoked", None)
        super().__init__(**kwargs)
        if is_rev is True:
            self.revoked_at = datetime.utcnow()
        elif is_rev is False:
            self.revoked_at = None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @is_revoked.setter
    def is_revoked(self, val: bool):
        if val:
            self.revoked_at = datetime.utcnow()
        else:
            self.revoked_at = None

class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    template_name = Column(String(100), index=True, nullable=False)
    category = Column(String(50), default="MARKETING")  # MARKETING or UTILITY
    language = Column(String(10), default="en")        # en, gu, hi
    header_text = Column(String(150), nullable=True)
    body_text = Column(Text, nullable=False)
    footer_text = Column(String(100), nullable=True)
    status = Column(String(50), default="APPROVED")     # APPROVED, PENDING, REJECTED
    # Configure-Once-Use-Everywhere: maps {{1}}, {{2}} ... to contact/cart/coupon/static fields
    variable_mappings = Column(JSON, nullable=True)     # e.g. {"1": {"type": "contact_field", "value": "name"}, "2": {...}}
    created_at = Column(DateTime, default=datetime.utcnow)

class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), nullable=False)
    rule_type = Column(String(50), nullable=False) # INACTIVE_DAYS, ORDER_COUNT_VIP, CART_RECOVERY
    trigger_condition = Column(String(100), nullable=False) # e.g. "days > 15", "orders >= 2", "cart_delay = 30m"
    threshold_value = Column(Integer, default=30)
    template_name = Column(String(100), nullable=False)
    coupon_code = Column(String(50), nullable=True)
    dedup_days = Column(Integer, default=7)
    variable_mappings = Column(JSON, nullable=True)  # e.g. {"1": {"type": "contact_field", "value": "name"}, "2": ...}
    is_active = Column(Boolean, default=True)
    total_triggered = Column(Integer, default=0)
    approval_status = Column(String(50), default="IDLE")  # IDLE, PENDING_APPROVAL, APPROVED
    pending_recipients_count = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)  # Optional end-date/deadline to auto-deactivate
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    customer_phone = Column(String(20), index=True, nullable=False)
    sender_type = Column(String(20), default="CUSTOMER")  # "CUSTOMER" (inbound) or "AGENT" (outbound)
    message_type = Column(String(20), default="text")      # text, template, image, document
    text = Column(Text, nullable=True)
    meta_message_id = Column(String(100), nullable=True, unique=True, index=True)
    status = Column(String(30), default="DELIVERED")      # RECEIVED, SENT, DELIVERED, READ, FAILED
    is_read = Column(Boolean, default=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowFlow(Base):
    __tablename__ = "workflow_flows"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(50), nullable=False, default="ABANDONED_CART")  # ABANDONED_CART, FESTIVAL_PROMO, INACTIVE_CUSTOMERS, ORDER_COUNT_VIP, MANUAL
    trigger_config = Column(JSON, default=dict)
    nodes = Column(JSON, nullable=False, default=list)  # [{id, type, label, data, position}]
    edges = Column(JSON, nullable=False, default=list)  # [{id, source, target, sourceHandle}]
    is_active = Column(Boolean, default=True)
    stats = Column(JSON, default=lambda: {"entered": 0, "completed": 0, "goals_converted": 0, "revenue_recovered": 0})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkflowSession(Base):
    __tablename__ = "workflow_sessions"

    id = Column(Integer, primary_key=True, index=True)
    flow_id = Column(Integer, index=True, nullable=False)
    customer_phone = Column(String(20), index=True, nullable=False)
    current_node_id = Column(String(50), nullable=True)
    state_data = Column(JSON, default=dict)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, WAITING_DELAY, WAITING_CONDITION, COMPLETED_GOAL, COMPLETED_DROPOUT, CANCELLED
    next_evaluation_at = Column(DateTime, default=datetime.utcnow, index=True)
    history = Column(JSON, default=list)
    # WP8: Worker lease columns for distributed job claiming
    claimed_by = Column(String(64), nullable=True)
    claimed_until = Column(DateTime, nullable=True, index=True)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IntegrationSecret(Base):
    __tablename__ = "integration_secrets"

    id = Column(Integer, primary_key=True, index=True)
    secret_reference = Column(String(100), unique=True, index=True, nullable=False)
    encrypted_value = Column(Text, nullable=False)
    nonce = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(100), nullable=True)
    target_id = Column(String(100), nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ExternalDataSource(Base):
    __tablename__ = "external_data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)               # e.g. "Store Live Customer API", "Shipping API"
    endpoint_url = Column(Text, nullable=False)               # e.g. https://store.example.com/api/crm-customer
    auth_method = Column(String(30), default="bearer")        # bearer, x_api_key, basic, none
    secret_reference = Column(String(100), nullable=True)     # Reference to encrypted integration_secrets table
    approved_hostname = Column(String(255), nullable=True)    # Exact approved hostname for credential binding
    purpose = Column(String(100), nullable=True, default="customer_lookup")
    lookup_param = Column(String(30), default="phone")       # query param key name (e.g. ?phone=...)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __init__(self, **kwargs):
        # WP3: Plaintext api_key is never stored on the model.
        # If legacy code/tests pass api_key, assign a secret_reference.
        api_key = kwargs.pop("api_key", None)
        kwargs.pop("header_name", None)
        if api_key and not kwargs.get("secret_reference"):
            # Mark that a secret reference exists for this legacy source
            kwargs["secret_reference"] = f"sec_ref_legacy_{abs(hash(api_key))}"
        super().__init__(**kwargs)

    @property
    def has_secret(self) -> bool:
        return bool(self.secret_reference and self.secret_reference.strip())

    @property
    def has_api_key(self) -> bool:
        return self.has_secret



class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InboundWebhookEvent(Base):
    __tablename__ = "inbound_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    provider_event_id = Column(String(128), nullable=False, index=True)
    event_type = Column(String(50), nullable=True)
    payload_hash = Column(String(64), nullable=True)
    correlation_id = Column(String(64), nullable=True)
    processed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_inbound_provider_event"),
    )


class OutboundMessage(Base):
    """
    WP2 — Central idempotency ledger for every outbound WhatsApp message.
    Created by authorize_outbound_message() BEFORE any Meta API call.
    Dispatch functions update status + meta_message_id after the call.
    Provides at-most-once delivery guarantee via idempotency_key unique constraint.
    """
    __tablename__ = "outbound_messages"

    id = Column(Integer, primary_key=True, index=True)

    # Idempotency — callers must provide a stable key; DB enforces uniqueness
    idempotency_key = Column(String(200), unique=True, index=True, nullable=False)

    # Recipient (always E.164)
    recipient_phone_e164 = Column(String(20), index=True, nullable=False)
    # Salted SHA-256 hash of recipient_phone_e164 for audit log storage (never raw phone in audit)
    recipient_hash = Column(String(64), nullable=False)

    # Message characteristics
    message_kind = Column(String(20), nullable=False)     # "template" | "free_text"
    purpose = Column(String(30), nullable=False)          # "marketing" | "utility" | "support"
    template_name = Column(String(100), nullable=True)

    # Relations
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True, index=True)
    workflow_session_id = Column(Integer, ForeignKey("workflow_sessions.id"), nullable=True, index=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    service_actor = Column(String(50), nullable=True)     # e.g. "scheduler", "cart_recovery"

    # Policy decision (recorded before dispatch)
    policy_decision = Column(String(20), nullable=False, default="authorized")  # "authorized" | "denied"
    policy_reason = Column(Text, nullable=True)

    # Dispatch outcome
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING | SENT | FAILED | SKIPPED
    meta_message_id = Column(String(100), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    dispatched_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
