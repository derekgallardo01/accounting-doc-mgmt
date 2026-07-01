from datetime import datetime, timedelta, timezone

from accounting_doc_mgmt.backend import MockSharePoint
from accounting_doc_mgmt.client_portal_provisioner import (
    DEFAULT_LINK_EXPIRY_DAYS,
    MockPortalClient,
    provision_client_portal,
)


def _fixture_matter_and_docs(matter_id: str = "m-01-tax-2026"):
    b = MockSharePoint()
    matter = next(m for m in b.list_matters() if m.id == matter_id)
    docs = b.list_documents(matter.id)
    return matter, docs


def test_provision_creates_guest_invite():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="contact@bakery.com", client_display_name="Owner - Bakery",
        portal_client=portal,
    )
    assert len(result.guest_invites) == 1
    assert result.guest_invites[0].email == "contact@bakery.com"
    assert result.guest_invites[0].matter_id == matter.id


def test_provision_creates_two_sharing_links():
    """One for Source Documents (client uploads), one for Deliverables (client sees)."""
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="contact@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    assert len(result.sharing_links) == 2
    libraries = {l.library for l in result.sharing_links}
    assert libraries == {"Source Documents", "Deliverables"}


def test_source_documents_link_is_edit_deliverables_is_view():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="contact@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    source_link = next(l for l in result.sharing_links if l.library == "Source Documents")
    deliv_link = next(l for l in result.sharing_links if l.library == "Deliverables")
    assert source_link.link_type == "edit"
    assert deliv_link.link_type == "view_only"


def test_default_link_expiry_matches_config():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal, now=now,
    )
    for link in result.sharing_links:
        assert link.expires_at == now + timedelta(days=DEFAULT_LINK_EXPIRY_DAYS)


def test_long_expiry_triggers_warning():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal, link_expiry_days=365,
    )
    assert any("expiry" in w.lower() for w in result.warnings)


def test_landing_page_flags_missing_source_docs():
    """The mock fixture matter has partial source docs (W-2 present, no 1099)."""
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    assert result.landing_page
    outstanding = [i for i in result.landing_page.items if i.status == "outstanding"]
    # W-2 is signed_off; 1099-Div is technically labeled "1099-Div" in filename
    # so should be received; Prior-year is likely outstanding.
    assert outstanding  # at least one item outstanding


def test_landing_page_renders_markdown_sections():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    md = result.landing_page.to_markdown()
    assert "# Client portal" in md
    # Should have at least one of the section headers
    assert any(h in md for h in ["## Please provide", "## Ready for your sign-off",
                                  "## Received", "## Completed"])


def test_revoke_sharing_link():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    revoked = portal.revoke_sharing_link(matter.id, "c@x.com", "Source Documents")
    assert revoked == 1
    active = portal.list_links(include_revoked=False)
    assert len(active) == 1


def test_summary_includes_counts():
    matter, docs = _fixture_matter_and_docs()
    portal = MockPortalClient()
    result = provision_client_portal(
        matter=matter, documents=docs,
        client_email="c@x.com", client_display_name="Owner",
        portal_client=portal,
    )
    s = result.summary()
    assert "guest invite" in s
    assert "sharing link" in s
