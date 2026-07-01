from accounting_doc_mgmt.approval_flow import (
    ApprovalDecision,
    export_power_automate_json,
    run_approval_flow,
)
from accounting_doc_mgmt.backend import MockSharePoint
from accounting_doc_mgmt.matter_provisioner import MatterSpec, provision_matter


def _seed_matter(backend: MockSharePoint, matter_id: str = "m-05-audit-2026"):
    spec = MatterSpec(
        matter_id=matter_id,
        client_id="c-05",
        kind="audit",
        year=2026,
        partner_upn="p@x.com",
        senior_upn="s@x.com",
    )
    provision_matter(spec, backend)
    return matter_id


def test_default_run_approves_workpapers():
    b = MockSharePoint()
    matter_id = _seed_matter(b)
    summary = run_approval_flow(b, matter_id)
    assert summary.total_documents > 0
    assert summary.approved == summary.total_documents


def test_reject_at_partner_marks_rejected():
    b = MockSharePoint()
    matter_id = _seed_matter(b)
    docs = b.list_documents(matter_id)
    workpaper = next(d for d in docs if d.doc_type == "workpaper")
    summary = run_approval_flow(b, matter_id, decision_map={
        workpaper.id: {"partner": ApprovalDecision.REJECT},
    })
    rejected_ids = [r.document_id for r in summary.runs if r.final_status in ("rejected", "dead_lettered")]
    assert workpaper.id in rejected_ids


def test_max_retries_leads_to_dead_letter():
    b = MockSharePoint()
    matter_id = _seed_matter(b)
    docs = b.list_documents(matter_id)
    workpaper = next(d for d in docs if d.doc_type == "workpaper")
    summary = run_approval_flow(b, matter_id, decision_map={
        workpaper.id: {"partner": ApprovalDecision.REJECT},
    })
    dl_doc = next(r for r in summary.runs if r.document_id == workpaper.id)
    assert dl_doc.retries == 2  # MAX_RETRIES
    assert dl_doc.final_status == "dead_lettered"


def test_abstain_final_status():
    b = MockSharePoint()
    matter_id = _seed_matter(b)
    docs = b.list_documents(matter_id)
    workpaper = next(d for d in docs if d.doc_type == "workpaper")
    summary = run_approval_flow(b, matter_id, decision_map={
        workpaper.id: {"partner": ApprovalDecision.ABSTAIN},
    })
    ab_doc = next(r for r in summary.runs if r.document_id == workpaper.id)
    assert ab_doc.final_status == "abstained"


def test_flow_summary_line_format():
    b = MockSharePoint()
    matter_id = _seed_matter(b)
    summary = run_approval_flow(b, matter_id)
    s = summary.summary()
    assert "approved" in s
    assert "rejected" in s
    assert "dead-lettered" in s


def test_export_power_automate_json_shape():
    p = export_power_automate_json("MyFlow")
    assert p["name"] == "MyFlow"
    assert "triggers" in p
    assert "actions" in p
    assert p["retry_policy"]["max_retries"] == 2
    assert "dead_letter_queue" in p
