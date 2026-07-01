from datetime import datetime, timedelta, timezone

from accounting_doc_mgmt.backend import MockSharePoint
from accounting_doc_mgmt.matter_provisioner import MatterSpec, provision_matter


def _spec(matter_id: str = "m-01-audit-2026", kind: str = "audit") -> MatterSpec:
    return MatterSpec(
        matter_id=matter_id,
        client_id="c-01",
        kind=kind,
        year=2026,
        partner_upn="p@x.com",
        senior_upn="s@x.com",
        staff_upns=["t1@x.com", "t2@x.com"],
        client_reviewer_upn="client@ridgeway.com",
        due_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )


def test_provision_creates_matter_in_backend():
    b = MockSharePoint()
    before = {m.id for m in b.list_matters()}
    result = provision_matter(_spec(), b)
    after = {m.id for m in b.list_matters()}
    assert (after - before) == {"m-01-audit-2026"}
    assert result.matter.status == "open"


def test_provision_creates_folders_across_libraries():
    b = MockSharePoint()
    result = provision_matter(_spec(), b)
    library_names = {folder.split("/")[0] for folder in result.folders_created}
    # All 4 default libraries should have folders
    assert library_names == {"Source Documents", "Workpapers", "Deliverables", "Correspondence"}


def test_provision_sets_permissions_for_all_roles():
    b = MockSharePoint()
    result = provision_matter(_spec(), b)
    roles = {p.role for p in result.permissions_set}
    assert {"Partner", "Senior Accountant", "Staff", "Client"}.issubset(roles)


def test_staff_upns_all_added():
    b = MockSharePoint()
    result = provision_matter(_spec(), b)
    staff = [p.principal_upn for p in result.permissions_set if p.role == "Staff"]
    assert set(staff) == {"t1@x.com", "t2@x.com"}


def test_provision_seeds_kind_appropriate_documents():
    b = MockSharePoint()
    audit_result = provision_matter(_spec("m-x-audit-2026", "audit"), b)
    assert any("audit-plan" in d.filename for d in audit_result.documents_seeded)

    b2 = MockSharePoint()
    tax_result = provision_matter(_spec("m-x-tax-2026", "tax_return"), b2)
    assert any("engagement-letter" in d.filename for d in tax_result.documents_seeded)

    b3 = MockSharePoint()
    q_result = provision_matter(_spec("m-x-q3-2026", "quarterly_review"), b3)
    assert any("review-checklist" in d.filename for d in q_result.documents_seeded)


def test_provision_summary_includes_counts():
    b = MockSharePoint()
    result = provision_matter(_spec(), b)
    s = result.summary()
    assert "folders" in s
    assert "seed docs" in s
    assert "permissions" in s


def test_client_reviewer_permission_is_optional():
    b = MockSharePoint()
    spec = _spec()
    spec.client_reviewer_upn = ""
    result = provision_matter(spec, b)
    client_perms = [p for p in result.permissions_set if p.role == "Client"]
    assert not client_perms
