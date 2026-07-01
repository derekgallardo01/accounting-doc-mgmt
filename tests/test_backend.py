from accounting_doc_mgmt.backend import MockSharePoint


def test_ships_ten_clients():
    b = MockSharePoint()
    assert len(b.list_clients()) == 10


def test_client_kinds_cover_all_three():
    b = MockSharePoint()
    kinds = {c.kind for c in b.list_clients()}
    assert kinds == {"individual", "small_business", "partnership"}


def test_every_client_has_at_least_one_matter():
    b = MockSharePoint()
    clients = b.list_clients()
    matters = b.list_matters()
    matter_client_ids = {m.client_id for m in matters}
    for c in clients:
        assert c.id in matter_client_ids


def test_individual_only_gets_tax_return():
    b = MockSharePoint()
    individuals = [c for c in b.list_clients() if c.kind == "individual"]
    for c in individuals:
        for m in b.list_matters(c.id):
            assert m.kind == "tax_return"


def test_business_clients_get_tax_and_quarterly():
    b = MockSharePoint()
    biz = [c for c in b.list_clients() if c.kind != "individual"]
    for c in biz:
        kinds = {m.kind for m in b.list_matters(c.id)}
        assert kinds == {"tax_return", "quarterly_review"}


def test_documents_seeded_per_matter():
    b = MockSharePoint()
    matters = b.list_matters()
    for m in matters:
        docs = b.list_documents(m.id)
        assert len(docs) == 5


def test_permissions_include_all_three_roles():
    b = MockSharePoint()
    perms = b.list_permissions("site")
    roles = {p.role for p in perms}
    assert {"Partner", "Senior Accountant", "Staff"}.issubset(roles)


def test_create_matter_appends_to_backend():
    b = MockSharePoint()
    from accounting_doc_mgmt.backend import Matter
    from datetime import datetime, timezone
    m = Matter(
        id="m-99-test", client_id="c-01", kind="advisory", year=2026,
        status="open", partner_upn="a", senior_upn="b",
        due_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    before = len(b.list_matters())
    b.create_matter(m)
    assert len(b.list_matters()) == before + 1
    assert any(x.id == "m-99-test" for x in b.list_matters())


def test_update_document_status():
    b = MockSharePoint()
    docs = b.list_documents()
    d = docs[0]
    b.update_document_status(d.id, "signed_off", approver="partner@x.com")
    updated = next(x for x in b.list_documents() if x.id == d.id)
    assert updated.review_status == "signed_off"
    assert updated.approver_upn == "partner@x.com"
