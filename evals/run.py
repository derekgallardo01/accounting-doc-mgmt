"""Eval harness with path-based assertions."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from accounting_doc_mgmt.approval_flow import run_approval_flow
from accounting_doc_mgmt.backend import MockSharePoint, NOW
from accounting_doc_mgmt.copilot_index import answer_query
from accounting_doc_mgmt.matter_provisioner import MatterSpec, provision_matter
from accounting_doc_mgmt.site_definition import DEFAULT_SITE, validate_site_definition


HERE = Path(__file__).parent


def _validate_default_site() -> dict:
    issues = validate_site_definition(DEFAULT_SITE)
    return {
        "issue_count": len(issues),
        "library_count": len(DEFAULT_SITE.libraries),
    }


def _backend_counts() -> dict:
    b = MockSharePoint()
    matters = b.list_matters()
    docs_per_matter = {m.id: len(b.list_documents(m.id)) for m in matters}
    return {
        "client_count": len(b.list_clients()),
        "matter_count": len(matters),
        "document_count_per_matter": docs_per_matter[matters[0].id],
    }


def _provision_audit_matter() -> dict:
    b = MockSharePoint()
    spec = MatterSpec(
        matter_id="m-eval-audit-2026",
        client_id="c-05",
        kind="audit",
        year=2026,
        partner_upn="p@x.com",
        senior_upn="s@x.com",
        staff_upns=["st@x.com"],
        client_reviewer_upn="client@x.com",
        due_date=NOW + timedelta(days=60),
    )
    result = provision_matter(spec, b)
    library_names = {f.split("/")[0] for f in result.folders_created}
    roles = {p.role for p in result.permissions_set}
    return {
        "folder_library_count": len(library_names),
        "permission_role_count": len(roles),
        "seed_doc_count": len(result.documents_seeded),
    }


def _approval_flow_default() -> dict:
    b = MockSharePoint()
    spec = MatterSpec(
        matter_id="m-eval-approval-2026",
        client_id="c-05",
        kind="audit",
        year=2026,
        partner_upn="p@x.com",
        senior_upn="s@x.com",
    )
    provision_matter(spec, b)
    summary = run_approval_flow(b, matter_id=spec.matter_id)
    return {
        "approved_count": summary.approved,
        "dead_lettered_count": summary.dead_lettered,
        "rejected_count": summary.rejected,
    }


def _copilot_matter_status() -> dict:
    b = MockSharePoint()
    ans = answer_query("What's the status of matter m-01-tax-2026?", b)
    return {"intent": ans.intent, "answer": ans.answer}


def _copilot_due_60() -> dict:
    b = MockSharePoint()
    ans = answer_query("Which matters are due in the next 60 days?", b)
    return {"intent": ans.intent, "matched_count": len(ans.matched_matters)}


def _copilot_unsigned() -> dict:
    b = MockSharePoint()
    ans = answer_query("Show me documents for Ridgeway Bakery that haven't been signed off", b)
    return {"intent": ans.intent, "matched_client_count": len(ans.matched_clients)}


def _capacity_forecast_default_firm() -> dict:
    from accounting_doc_mgmt.capacity_planner import DEFAULT_FIRM, forecast_capacity
    b = MockSharePoint()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=52)
    return {
        "horizon_weeks": forecast.horizon_weeks,
        "bottleneck_count": len(forecast.bottleneck_weeks),
        "hiring_suggestion_count": len(forecast.hiring),
        "outsource_suggestion_count": len(forecast.outsource),
    }


def _capacity_forecast_huge_firm() -> dict:
    from accounting_doc_mgmt.capacity_planner import Staff, forecast_capacity
    b = MockSharePoint()
    huge_firm = [
        Staff("a@x.com", "A", "Partner", 200.0),
        Staff("b@x.com", "B", "Senior Accountant", 400.0),
        Staff("c@x.com", "C", "Staff", 200.0),
    ]
    forecast = forecast_capacity(b, staff=huge_firm, horizon_weeks=52)
    return {
        "bottleneck_count": len(forecast.bottleneck_weeks),
        "hiring_suggestion_count": len(forecast.hiring),
        "outsource_suggestion_count": len(forecast.outsource),
    }


def _client_portal_provision() -> dict:
    from accounting_doc_mgmt.client_portal_provisioner import (
        MockPortalClient, provision_client_portal,
    )
    b = MockSharePoint()
    matter = next(m for m in b.list_matters() if m.id == "m-01-tax-2026")
    docs = b.list_documents(matter.id)
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="contact@bakery.com", client_display_name="Owner - Bakery",
        portal_client=portal,
    )
    source_link = next(l for l in result.sharing_links if l.library == "Source Documents")
    deliv_link = next(l for l in result.sharing_links if l.library == "Deliverables")
    return {
        "guest_invite_count": len(result.guest_invites),
        "sharing_link_count": len(result.sharing_links),
        "source_link_is_edit": source_link.link_type == "edit",
        "deliverables_link_is_view": deliv_link.link_type == "view_only",
    }


def _client_portal_landing_page() -> dict:
    from accounting_doc_mgmt.client_portal_provisioner import (
        MockPortalClient, provision_client_portal,
    )
    b = MockSharePoint()
    matter = next(m for m in b.list_matters() if m.id == "m-01-tax-2026")
    docs = b.list_documents(matter.id)
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    outstanding = [i for i in result.landing_page.items if i.status == "outstanding"]
    md = result.landing_page.to_markdown()
    return {
        "outstanding_count": len(outstanding),
        "markdown_has_please_provide": "## Please provide" in md,
    }


OPS = {
    "validate_default_site": _validate_default_site,
    "backend_counts": _backend_counts,
    "provision_audit_matter": _provision_audit_matter,
    "approval_flow_default": _approval_flow_default,
    "copilot_matter_status": _copilot_matter_status,
    "copilot_due_60": _copilot_due_60,
    "copilot_unsigned": _copilot_unsigned,
    "capacity_forecast_default_firm": _capacity_forecast_default_firm,
    "capacity_forecast_huge_firm": _capacity_forecast_huge_firm,
    "client_portal_provision": _client_portal_provision,
    "client_portal_landing_page": _client_portal_landing_page,
}


def _lookup(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
        if obj is None:
            return None
    return obj


def _check(result: dict, a: dict) -> tuple[bool, str]:
    value = _lookup(result, a["path"])
    if "eq" in a:
        ok = value == a["eq"]
        return ok, f"{a['path']} = {value} (expected {a['eq']})"
    if "gte" in a:
        ok = value is not None and value >= a["gte"]
        return ok, f"{a['path']} = {value} (expected >= {a['gte']})"
    if "contains" in a:
        ok = value is not None and a["contains"] in str(value)
        return ok, f"{a['path']} = {value!r} (expected to contain {a['contains']!r})"
    return False, "unknown assertion"


def main() -> int:
    golden = json.loads((HERE / "golden.json").read_text())
    passed_cases = 0
    failed_cases = 0

    print(f"Running {len(golden['cases'])} eval cases...\n")

    for case in golden["cases"]:
        result = OPS[case["op"]]()
        case_ok = True
        for a in case["assertions"]:
            ok, msg = _check(result, a)
            marker = "PASS" if ok else "FAIL"
            print(f"  [{marker}] {case['name']} :: {msg}")
            case_ok = case_ok and ok
        if case_ok:
            passed_cases += 1
        else:
            failed_cases += 1
        print()

    print(f"Result: {passed_cases}/{passed_cases + failed_cases} cases passed")
    return 0 if failed_cases == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
