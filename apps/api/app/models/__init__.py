"""Import every model so Base.metadata is fully populated (create_all / autogenerate)."""
from app.models.organization import (  # noqa: F401
    Organization,
    LegalEntity,
    Property,
    Building,
    Unit,
)
from app.models.identity import User, Delegation  # noqa: F401
from app.models.vendor import Vendor, VendorAlias, VendorRiskEvent  # noqa: F401
from app.models.commercial import (  # noqa: F401
    Project,
    CostCode,
    WorkOrder,
    PurchaseOrder,
    POLine,
    Contract,
    ContractRate,
    ChangeOrder,
)
from app.models.finance import (  # noqa: F401
    GLAccount,
    Budget,
    BudgetLine,
    Payment,
    Export,
)
from app.models.invoice import (  # noqa: F401
    Invoice,
    InvoiceFile,
    InvoiceLineItem,
    InvoiceBlob,
    FieldProvenance,
)
from app.models.workflow import (  # noqa: F401
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStep,
    Exception_,
    Notification,
)
from app.models.ai_audit import (  # noqa: F401
    ModelRun,
    ToolCall,
    MatchResult,
    AnomalyFlag,
    FeedbackLabel,
    AuditEvent,
    Outbox,
    ProcessedEvent,
)

__all__ = ["Organization"]
