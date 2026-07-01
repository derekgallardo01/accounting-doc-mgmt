"""SharePoint + Power Automate doc/PM kit for accounting firms."""
from accounting_doc_mgmt.backend import Client, Document, MockSharePoint, Matter, get_backend
from accounting_doc_mgmt.capacity_planner import (
    CapacityForecast,
    HiringSuggestion,
    OutsourceSuggestion,
    Staff,
    WeeklySlot,
    DEFAULT_EFFORT_ESTIMATES,
    DEFAULT_FIRM,
    forecast_capacity,
)
from accounting_doc_mgmt.client_portal_provisioner import (
    GuestInvite,
    LandingPage,
    LandingPageItem,
    MockPortalClient,
    ProvisioningResult,
    SharingLink,
    provision_client_portal,
)
from accounting_doc_mgmt.matter_provisioner import (
    MatterSpec,
    ProvisionResult,
    provision_matter,
)
from accounting_doc_mgmt.approval_flow import (
    ApprovalDecision,
    ApprovalRun,
    ApprovalStep,
    FlowRunSummary,
    run_approval_flow,
)
from accounting_doc_mgmt.copilot_index import CopilotAnswer, answer_query
from accounting_doc_mgmt.site_definition import SiteDefinition, load_site_definition

__all__ = [
    "Client",
    "Document",
    "MockSharePoint",
    "Matter",
    "get_backend",
    "MatterSpec",
    "ProvisionResult",
    "provision_matter",
    "ApprovalDecision",
    "ApprovalRun",
    "ApprovalStep",
    "FlowRunSummary",
    "run_approval_flow",
    "CopilotAnswer",
    "answer_query",
    "SiteDefinition",
    "load_site_definition",
    "CapacityForecast",
    "HiringSuggestion",
    "OutsourceSuggestion",
    "Staff",
    "WeeklySlot",
    "DEFAULT_EFFORT_ESTIMATES",
    "DEFAULT_FIRM",
    "forecast_capacity",
    "GuestInvite",
    "LandingPage",
    "LandingPageItem",
    "MockPortalClient",
    "ProvisioningResult",
    "SharingLink",
    "provision_client_portal",
]
