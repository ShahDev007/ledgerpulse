"""Domain enums shared across models and services."""
from __future__ import annotations

import enum


class InvoiceStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    MATCHED = "MATCHED"
    EXCEPTION = "EXCEPTION"
    APPROVAL_PENDING = "APPROVAL_PENDING"
    APPROVED = "APPROVED"
    EXPORTED = "EXPORTED"
    PAYMENT_SCHEDULED = "PAYMENT_SCHEDULED"
    PAID = "PAID"
    RECONCILED = "RECONCILED"
    REJECTED = "REJECTED"
    VOIDED = "VOIDED"


TERMINAL_STATUSES = {InvoiceStatus.RECONCILED, InvoiceStatus.REJECTED, InvoiceStatus.VOIDED}


class SourceType(str, enum.Enum):
    UPLOAD = "UPLOAD"
    EMAIL = "EMAIL"
    API = "API"
    BATCH = "BATCH"
    MOBILE = "MOBILE"


class ExceptionSeverity(str, enum.Enum):
    INFO = "INFO"
    REVIEW = "REVIEW"
    BLOCKING = "BLOCKING"


class ExceptionCategory(str, enum.Enum):
    DOCUMENT = "DOCUMENT"
    IDENTITY = "IDENTITY"
    COMMERCIAL = "COMMERCIAL"
    FINANCIAL = "FINANCIAL"
    APPROVAL = "APPROVAL"
    INTEGRATION = "INTEGRATION"
    PAYMENT = "PAYMENT"


class ApprovalDecision(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REQUEST_INFO = "REQUEST_INFO"
    DELEGATED = "DELEGATED"


class ApprovalStepStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"


class PaymentStatus(str, enum.Enum):
    NONE = "NONE"
    SCHEDULED = "SCHEDULED"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    MISMATCH = "MISMATCH"


class ExportStatus(str, enum.Enum):
    NOT_EXPORTED = "NOT_EXPORTED"
    EXPORTED = "EXPORTED"
    FAILED = "FAILED"


class CapexOpex(str, enum.Enum):
    CAPEX = "CAPEX"
    OPEX = "OPEX"


class AuditActorType(str, enum.Enum):
    USER = "USER"
    RULE = "RULE"
    MODEL = "MODEL"
    INTEGRATION = "INTEGRATION"
    SYSTEM = "SYSTEM"


# Personas / roles (RBAC capability is derived from role in app.auth.permissions)
class Role(str, enum.Enum):
    AP_ACCOUNTANT = "AP_ACCOUNTANT"
    PROPERTY_MANAGER = "PROPERTY_MANAGER"
    CONSTRUCTION_PM = "CONSTRUCTION_PM"
    ASSET_MANAGER = "ASSET_MANAGER"
    FINANCE_ADMIN = "FINANCE_ADMIN"
    DIRECTOR_FINANCE = "DIRECTOR_FINANCE"
    AUDITOR = "AUDITOR"
