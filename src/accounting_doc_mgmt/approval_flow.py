"""Power Automate approval flow simulator.

Represents an approval flow as a sequence of steps:

    (a) Detect new / modified deliverable in the library
    (b) Route to preparer for self-review
    (c) Route to senior for review
    (d) Route to partner for sign-off
    (e) On any rejection: notify preparer + set status to draft
    (f) On approval at every step: set status to signed_off + notify client

The simulator runs the flow end-to-end against the mock backend and
reports a `FlowRunSummary` with per-step actions + final decision. The
Power Automate JSON definition (Power Automate's Flow schema) is
exported from the same object model so a real flow can be deployed to
the tenant via the Flow API. See docs/customization.md.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from accounting_doc_mgmt.backend import Document, MockSharePoint


class ApprovalDecision(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ABSTAIN = "abstain"


@dataclass
class ApprovalStep:
    step_name: str
    approver_role: str  # "preparer" | "senior" | "partner"
    approver_upn: str
    decision: ApprovalDecision
    comment: str = ""


@dataclass
class ApprovalRun:
    document_id: str
    steps: list[ApprovalStep] = field(default_factory=list)
    final_status: str = "in_review"  # or "signed_off" / "rejected"
    retries: int = 0


@dataclass
class FlowRunSummary:
    total_documents: int = 0
    approved: int = 0
    rejected: int = 0
    abstained: int = 0
    dead_lettered: int = 0  # too many retries
    runs: list[ApprovalRun] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Approval flow: {self.total_documents} docs | "
            f"{self.approved} approved | {self.rejected} rejected | "
            f"{self.abstained} abstained | {self.dead_lettered} dead-lettered"
        )


MAX_RETRIES = 2


def run_approval_flow(
    backend: MockSharePoint,
    matter_id: str,
    decision_map: dict[str, dict[str, ApprovalDecision]] | None = None,
) -> FlowRunSummary:
    """Simulate the flow for every deliverable/workpaper in a matter.

    `decision_map` optionally overrides the default decisions per document
    per role, so tests can force approve/reject paths.
    """
    documents = [d for d in backend.list_documents(matter_id)
                 if d.doc_type in ("workpaper", "deliverable")]

    summary = FlowRunSummary(total_documents=len(documents))
    all_perms_by_role: dict[str, str] = {}
    for perm in backend.list_permissions(matter_id):
        all_perms_by_role[perm.role] = perm.principal_upn

    partner = all_perms_by_role.get("Partner", "unknown-partner")
    senior = all_perms_by_role.get("Senior Accountant", "unknown-senior")

    for doc in documents:
        run = _run_single(doc, partner=partner, senior=senior,
                          decision_map=(decision_map or {}).get(doc.id, {}))
        summary.runs.append(run)

        if run.final_status == "signed_off":
            summary.approved += 1
            backend.update_document_status(doc.id, "signed_off", approver=partner)
        elif run.final_status == "rejected":
            summary.rejected += 1
            backend.update_document_status(doc.id, "draft")
        elif run.final_status == "abstained":
            summary.abstained += 1
        elif run.final_status == "dead_lettered":
            summary.dead_lettered += 1

    return summary


def _run_single(doc: Document, partner: str, senior: str,
                decision_map: dict[str, ApprovalDecision]) -> ApprovalRun:
    run = ApprovalRun(document_id=doc.id)

    for attempt in range(MAX_RETRIES + 1):
        preparer_upn = doc.uploaded_by
        preparer_decision = decision_map.get("preparer", ApprovalDecision.APPROVE)
        run.steps.append(ApprovalStep(
            step_name="self_review",
            approver_role="preparer",
            approver_upn=preparer_upn,
            decision=preparer_decision,
        ))
        if preparer_decision == ApprovalDecision.REJECT:
            run.retries = attempt
            run.final_status = "rejected"
            if attempt == MAX_RETRIES:
                run.final_status = "dead_lettered"
                return run
            continue

        senior_decision = decision_map.get("senior", ApprovalDecision.APPROVE)
        run.steps.append(ApprovalStep(
            step_name="senior_review",
            approver_role="senior",
            approver_upn=senior,
            decision=senior_decision,
        ))
        if senior_decision == ApprovalDecision.REJECT:
            run.retries = attempt
            run.final_status = "rejected"
            if attempt == MAX_RETRIES:
                run.final_status = "dead_lettered"
                return run
            continue

        partner_decision = decision_map.get("partner", ApprovalDecision.APPROVE)
        run.steps.append(ApprovalStep(
            step_name="partner_signoff",
            approver_role="partner",
            approver_upn=partner,
            decision=partner_decision,
        ))
        if partner_decision == ApprovalDecision.APPROVE:
            run.retries = attempt
            run.final_status = "signed_off"
            return run
        if partner_decision == ApprovalDecision.ABSTAIN:
            run.retries = attempt
            run.final_status = "abstained"
            return run
        # Partner rejected - retry if under limit, else dead-letter
        run.retries = attempt
        run.final_status = "rejected"
        if attempt == MAX_RETRIES:
            run.final_status = "dead_lettered"
            return run
        continue

    return run


def export_power_automate_json(flow_name: str = "AccountingApprovalFlow") -> dict[str, Any]:
    """Export the flow definition as a Power Automate JSON payload.

    Not a real end-to-end Flow JSON (that requires environment ids etc.)
    but the shape a delivery engineer maps onto Power Automate Designer
    when wiring the real flow.
    """
    return {
        "name": flow_name,
        "triggers": [
            {
                "type": "sharepoint.OnItemCreatedOrModified",
                "library": "Deliverables",
                "filter": "review_status eq 'draft' or review_status eq 'in_review'"
            }
        ],
        "actions": [
            {"type": "SendApprovalRequest", "assignee": "@{item.uploaded_by}", "step": "self_review"},
            {"type": "IfApproved.SendApprovalRequest", "assignee": "@{matter.senior_upn}", "step": "senior_review"},
            {"type": "IfApproved.SendApprovalRequest", "assignee": "@{matter.partner_upn}", "step": "partner_signoff"},
            {"type": "OnApproved.UpdateItem", "column": "review_status", "value": "signed_off"},
            {"type": "OnRejected.UpdateItem", "column": "review_status", "value": "draft"},
            {"type": "OnRejected.SendEmail",
             "to": "@{item.uploaded_by}", "subject": "Approval rejected: @{item.filename}"},
        ],
        "retry_policy": {"max_retries": MAX_RETRIES, "backoff_hours": 24},
        "dead_letter_queue": "sharepoint_list://Flow-DLQ",
    }
