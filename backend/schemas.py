from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator

from services.phone_service import normalize_phone, InvalidPhoneNumberError


class ContactCreate(BaseModel):
    phone: str = Field(..., description="Customer phone in international format e.g. +919876543210")
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=120)
    city: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=255)
    total_orders: Optional[int] = Field(default=0, ge=0)
    last_order_date: Optional[datetime] = None
    birth_day: Optional[int] = Field(None, ge=1, le=31)
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    custom_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))


class ContactUpdate(BaseModel):
    phone: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    tags: Optional[str] = None
    total_orders: Optional[int] = None
    last_order_date: Optional[datetime] = None
    assigned_user_id: Optional[int] = None
    custom_attributes: Optional[Dict[str, Any]] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))


class ContactResponse(BaseModel):
    id: int
    phone: str
    name: Optional[str]
    email: Optional[str]
    total_orders: int
    last_order_date: Optional[datetime] = None
    city: Optional[str] = None
    tags: Optional[str] = None
    birth_day: Optional[int] = None
    birth_month: Optional[int] = None
    is_active: bool
    assigned_user_id: Optional[int] = None
    custom_attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ContactListItemResponse(BaseModel):
    id: int
    phone: str
    name: Optional[str] = None
    email: Optional[str] = None
    total_orders: int = 0
    last_order_date: Optional[datetime] = None
    city: Optional[str] = None
    tags: Optional[str] = None
    birth_day: Optional[int] = None
    birth_month: Optional[int] = None
    is_active: bool = True
    assigned_user_id: Optional[int] = None
    custom_attributes: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CustomerSyncPayload(BaseModel):
    phone: str = Field(..., description="Customer phone number (e.g. +919876543210 or 9876543210)")
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=120)
    city: Optional[str] = Field(None, max_length=100)
    tags: Optional[str] = Field(None, max_length=255)
    total_orders: Optional[int] = Field(None, ge=0)
    last_order_date: Optional[datetime] = None
    birth_day: Optional[int] = Field(None, ge=1, le=31)
    birth_month: Optional[int] = Field(None, ge=1, le=12)
    custom_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class ContactAssignRequest(BaseModel):
    assigned_user_id: Optional[int] = Field(None, description="User ID to assign contact to (or null to unassign)")


class ContactExportRequest(BaseModel):
    password: str = Field(..., description="Admin account password")
    two_factor_code: Optional[str] = Field(None, description="2FA OTP code if enabled")
    reason: str = Field(..., min_length=5, description="Business justification for PII export")



class DiscountCodeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    discount_type: str = Field(default="PERCENT", description="PERCENT or FLAT")
    discount_value: float = Field(..., gt=0)
    min_order_value: Optional[float] = Field(default=0.0, ge=0)
    max_uses: Optional[int] = Field(default=1000, ge=1)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = True


class DiscountCodeResponse(BaseModel):
    id: int
    code: str
    discount_type: str
    discount_value: float
    min_order_value: float
    max_uses: int
    used_count: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CartEventPayload(BaseModel):
    cart_token: str = Field(..., max_length=100)
    customer_phone: str = Field(..., description="Customer phone number")
    cart_value: float = Field(default=0.0, ge=0)
    items: List[dict] = Field(default_factory=list)
    customer_name: Optional[str] = None
    first_name: Optional[str] = None
    delivery_address: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary key-value store payload fields")

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))


class OrderCompletedPayload(BaseModel):
    cart_token: str = Field(..., max_length=100)
    customer_phone: str = Field(..., description="Customer phone number")

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))


class ExternalDataSourceCreate(BaseModel):
    name: str = Field(..., max_length=100)
    endpoint_url: str = Field(..., description="Full URL e.g. https://store.example.com/api/crm-customer")
    auth_method: Optional[str] = "bearer"  # bearer, x_api_key, basic, none
    api_key: Optional[str] = None         # Secret to encrypt (never returned or saved plaintext)
    approved_hostname: Optional[str] = None
    purpose: Optional[str] = "customer_lookup"
    lookup_param: Optional[str] = "phone"
    is_active: Optional[bool] = True
    password: Optional[str] = None
    two_factor_code: Optional[str] = None


class ExternalDataSourceUpdate(BaseModel):
    name: Optional[str] = None
    endpoint_url: Optional[str] = None
    auth_method: Optional[str] = None
    api_key: Optional[str] = None
    approved_hostname: Optional[str] = None
    purpose: Optional[str] = None
    lookup_param: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    two_factor_code: Optional[str] = None


class ExternalDataSourceResponse(BaseModel):
    id: int
    name: str
    endpoint_url: str
    auth_method: str
    secret_reference: Optional[str] = None
    approved_hostname: Optional[str] = None
    purpose: Optional[str] = None
    has_secret: bool = False
    has_api_key: bool = False
    lookup_param: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ExternalDataSourceTestRequest(BaseModel):
    test_phone: Optional[str] = "+919876543210"
    password: Optional[str] = None
    two_factor_code: Optional[str] = None


class ExternalDataSourceTestResponse(BaseModel):
    status_code: int
    is_success: bool
    latency_ms: float
    correlation_id: str
    message: str



class OptOutRequest(BaseModel):
    phone: str = Field(...)
    reason: Optional[str] = "USER_REQUEST"

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))

class CampaignCreate(BaseModel):
    title: str = Field(..., max_length=150)
    template_name: str = Field(..., max_length=100)
    language: Optional[str] = "en"
    target_filter: Optional[str] = "ALL"  # ALL, INACTIVE_30_DAYS, HIGH_VALUE
    per_day_limit: Optional[int] = None  # Cap on max messages to send per day/run
    scheduled_for: Optional[str] = None  # ISO timestamp or datetime string
    custom_phones: Optional[List[str]] = None  # Optional list of explicit phone numbers
    # 🔐 Security step-up authentication fields
    password: Optional[str] = None
    two_factor_code: Optional[str] = None

    @field_validator("custom_phones")
    @classmethod
    def validate_custom_phones(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if not v:
            return v
        normalized = []
        for p in v:
            try:
                normalized.append(normalize_phone(p))
            except InvalidPhoneNumberError as e:
                raise ValueError(f"Invalid phone in custom_phones list '{p}': {e}")
        return normalized


class RuleApproveRequest(BaseModel):
    password: str = Field(..., description="User account password to authorize high-volume send")
    two_factor_code: Optional[str] = Field(None, description="6-digit TOTP or Email OTP code")


class CampaignResponse(BaseModel):
    id: int
    title: str
    template_name: str
    language: Optional[str] = "en"
    target_filter: Optional[str] = "ALL"
    status: Optional[str] = "DRAFT"
    total_recipients: Optional[int] = 0
    successful_sends: Optional[int] = 0
    failed_sends: Optional[int] = 0
    per_day_limit: Optional[int] = None
    scheduled_for: Optional[Union[datetime, str]] = None
    error_message: Optional[str] = None
    created_at: Optional[Union[datetime, str]] = None

    class Config:
        from_attributes = True


class TemplateCreate(BaseModel):
    template_name: str = Field(..., min_length=2, max_length=100)
    category: str = Field(default="MARKETING")
    language: str = Field(default="en")
    body_text: str = Field(..., min_length=5)
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    variable_mappings: Optional[Dict[str, Any]] = None  # {"1": {"type": "contact_field", "value": "name"}, ...}


class TemplateUpdateMappings(BaseModel):
    variable_mappings: Optional[Dict[str, Any]] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=120)
    password: str = Field(..., min_length=6)
    role: str = Field(default="agent", pattern="^(admin|manager|agent)$")
    can_support_send: Optional[bool] = False


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|agent|service|manager)$")
    can_support_send: Optional[bool] = None


class AdminUserPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6, description="New user password (minimum 6 characters)")


class AdminToggle2FARequest(BaseModel):
    enabled: bool = Field(..., description="Enable or disable 2FA for this user")


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: Optional[str] = None
    role: Optional[str] = None
    requires_2fa: Optional[bool] = False
    temp_token: Optional[str] = None
    refresh_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_2fa_enabled: Optional[bool] = False
    role: str = "agent"
    auth_version: int = 1
    can_support_send: bool = False

    class Config:
        from_attributes = True


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str
    qr_code_base64: str


class TwoFactorVerifyRequest(BaseModel):
    code: str
    temp_token: Optional[str] = None


class TwoFactorDisableRequest(BaseModel):
    password: str


class AutomationRuleCreate(BaseModel):
    rule_name: str = Field(..., max_length=100)
    rule_type: str = Field(...) # INACTIVE_DAYS, ORDER_COUNT_VIP, CART_RECOVERY
    trigger_condition: str = Field(...)
    threshold_value: int = Field(default=30, ge=1)
    template_name: str = Field(...)
    coupon_code: Optional[str] = None
    dedup_days: int = Field(default=7, ge=1)
    variable_mappings: Optional[dict] = None
    expires_at: Optional[datetime] = None
    is_active: bool = True

class AutomationRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    trigger_condition: Optional[str] = None
    template_name: Optional[str] = None
    is_active: Optional[bool] = None
    threshold_value: Optional[int] = None
    coupon_code: Optional[str] = None
    dedup_days: Optional[int] = None
    variable_mappings: Optional[dict] = None
    expires_at: Optional[datetime] = None


class ChatSendMessageRequest(BaseModel):
    customer_phone: str = Field(..., description="Customer WhatsApp phone number e.g. +919876543210")
    text: str = Field(..., min_length=1, description="Message text content to send to customer")

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, v: str) -> str:
        try:
            return normalize_phone(v)
        except InvalidPhoneNumberError as e:
            raise ValueError(str(e))


class ChatMessageResponse(BaseModel):
    id: int
    customer_phone: str
    sender_type: str
    message_type: str
    text: Optional[str]
    meta_message_id: Optional[str]
    status: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChatConversationSummary(BaseModel):
    customer_phone: str
    customer_name: Optional[str] = "Customer"
    customer_city: Optional[str] = None
    total_orders: int = 0
    unread_count: int = 0
    last_message_text: Optional[str] = None
    last_message_time: Optional[datetime] = None
    last_sender: Optional[str] = None


class WorkflowFlowCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: Optional[str] = None
    trigger_type: str = Field(default="ABANDONED_CART")
    trigger_config: Optional[dict] = None
    nodes: list = Field(default_factory=list)
    edges: list = Field(default_factory=list)
    is_active: bool = True


class WorkflowFlowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_config: Optional[dict] = None
    nodes: Optional[list] = None
    edges: Optional[list] = None
    is_active: Optional[bool] = None


class WorkflowFlowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    trigger_type: str
    trigger_config: Optional[dict] = None
    nodes: list = Field(default_factory=list)
    edges: list = Field(default_factory=list)
    is_active: bool
    stats: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowSessionResponse(BaseModel):
    id: int
    flow_id: int
    customer_phone: str
    current_node_id: Optional[str] = None
    state_data: Optional[dict] = None
    status: str
    next_evaluation_at: datetime
    history: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyLimitUpdateRequest(BaseModel):
    daily_limit: int = Field(..., ge=1, le=500000, description="Maximum outbound WhatsApp messages allowed per 24 hours")
