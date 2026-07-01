"""Client portal provisioning.

Small accounting firms typically start with clients emailing PDFs
around. That works until the firm gets audited on data handling and
someone asks 'where's the audit trail for who accessed which W-2?'.
The client portal is the answer: guest access to a specific matter's
document library, with expiring share links, per-matter role
authorization, and a landing page that shows what's due from the
client.

This module provisions the portal side of the site definition:

- **Guest permissions** — invite the client contact to specific
  matter libraries only (never the whole site)
- **Sharing link expiry** — every share link auto-expires per the
  firm's data-handling policy
- **Client landing page** — a summary page showing outstanding items
  the client needs to provide (source documents), what's been
  received, what's ready for their sign-off

The kit ships a `MockPortalClient` for testing. Set
`GRAPH_BACKEND=graph` and provide app-reg env vars to swap to real
SharePoint external sharing APIs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from accounting_doc_mgmt.backend import Document, Matter, MockSharePoint, NOW


DEFAULT_LINK_EXPIRY_DAYS = 90
DEFAULT_LINK_TYPE = "view_only"  # or "edit"


@dataclass
class GuestInvite:
    email: str
    display_name: str
    matter_id: str
    role: str = "Client"


@dataclass
class SharingLink:
    matter_id: str
    library: str
    guest_email: str
    link_type: str  # "view_only" | "edit"
    expires_at: datetime
    revoked: bool = False


@dataclass
class LandingPageItem:
    """One row on the client's landing page."""

    matter_id: str
    matter_kind: str
    heading: str
    status: str  # "outstanding" | "received" | "ready_for_signoff" | "signed_off"
    action_needed: str = ""


@dataclass
class LandingPage:
    client_name: str
    client_email: str
    items: list[LandingPageItem] = field(default_factory=list)
    generated_at: datetime = field(default_factory=lambda: NOW)

    def to_markdown(self) -> str:
        parts = [f"# Client portal - {self.client_name}", ""]
        parts.append(f"*Last updated {self.generated_at.date()}*")
        parts.append("")

        outstanding = [i for i in self.items if i.status == "outstanding"]
        received = [i for i in self.items if i.status == "received"]
        signoff = [i for i in self.items if i.status == "ready_for_signoff"]
        done = [i for i in self.items if i.status == "signed_off"]

        if outstanding:
            parts.append("## Please provide")
            for i in outstanding:
                parts.append(f"- **{i.heading}** - {i.action_needed}")
            parts.append("")
        if signoff:
            parts.append("## Ready for your sign-off")
            for i in signoff:
                parts.append(f"- **{i.heading}** - {i.action_needed}")
            parts.append("")
        if received:
            parts.append("## Received - being reviewed by our team")
            for i in received:
                parts.append(f"- {i.heading}")
            parts.append("")
        if done:
            parts.append("## Completed")
            for i in done:
                parts.append(f"- {i.heading}")
            parts.append("")

        return "\n".join(parts)


@dataclass
class ProvisioningResult:
    matter_id: str
    guest_invites: list[GuestInvite] = field(default_factory=list)
    sharing_links: list[SharingLink] = field(default_factory=list)
    landing_page: LandingPage | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Portal provisioning for {self.matter_id}: "
            f"{len(self.guest_invites)} guest invite(s), "
            f"{len(self.sharing_links)} sharing link(s)"
            + (f", {len(self.warnings)} warning(s)" if self.warnings else "")
        )


class MockPortalClient:
    """In-memory portal client used by tests + demos."""

    def __init__(self) -> None:
        self._invites: list[GuestInvite] = []
        self._links: list[SharingLink] = []

    def invite_guest(self, invite: GuestInvite) -> None:
        self._invites.append(invite)

    def create_sharing_link(self, link: SharingLink) -> None:
        self._links.append(link)

    def revoke_sharing_link(self, matter_id: str, guest_email: str, library: str) -> int:
        """Return count of links revoked."""
        n = 0
        for link in self._links:
            if (link.matter_id == matter_id and link.guest_email == guest_email
                    and link.library == library and not link.revoked):
                link.revoked = True
                n += 1
        return n

    def list_invites(self) -> list[GuestInvite]:
        return list(self._invites)

    def list_links(self, include_revoked: bool = False) -> list[SharingLink]:
        return [l for l in self._links if include_revoked or not l.revoked]


def provision_client_portal(
    matter: Matter,
    documents: list[Document],
    client_email: str,
    client_display_name: str,
    portal_client: MockPortalClient | None = None,
    link_expiry_days: int = DEFAULT_LINK_EXPIRY_DAYS,
    now: datetime | None = None,
) -> ProvisioningResult:
    """Provision guest access + sharing links + landing page for one matter."""
    portal_client = portal_client or MockPortalClient()
    now = now or NOW

    result = ProvisioningResult(matter_id=matter.id)

    # Guest invite
    invite = GuestInvite(
        email=client_email,
        display_name=client_display_name,
        matter_id=matter.id,
    )
    portal_client.invite_guest(invite)
    result.guest_invites.append(invite)

    # Sharing links for the two libraries the client interacts with:
    # Source Documents (client uploads) + Deliverables (client sees final)
    expiry = now + timedelta(days=link_expiry_days)
    for library in ("Source Documents", "Deliverables"):
        link_type = "edit" if library == "Source Documents" else "view_only"
        link = SharingLink(
            matter_id=matter.id,
            library=library,
            guest_email=client_email,
            link_type=link_type,
            expires_at=expiry,
        )
        portal_client.create_sharing_link(link)
        result.sharing_links.append(link)

    # Landing page
    result.landing_page = _build_landing_page(matter, documents, client_display_name, client_email)

    # Warnings
    if link_expiry_days > 180:
        result.warnings.append(
            f"Sharing link expiry set to {link_expiry_days} days; recommend <= 90 days "
            "per data-handling policy."
        )

    return result


def _build_landing_page(
    matter: Matter,
    documents: list[Document],
    client_name: str,
    client_email: str,
) -> LandingPage:
    page = LandingPage(client_name=client_name, client_email=client_email)

    # Items the client needs to provide (based on matter kind)
    if matter.kind == "tax_return":
        expected_source_docs = ["W-2", "1099-Div", "Prior-year return"]
        received_filenames = {d.filename.lower() for d in documents if d.doc_type == "source"}
        for exp in expected_source_docs:
            already_received = any(exp.lower() in fn for fn in received_filenames)
            if already_received:
                page.items.append(LandingPageItem(
                    matter_id=matter.id, matter_kind=matter.kind,
                    heading=exp, status="received",
                    action_needed="",
                ))
            else:
                page.items.append(LandingPageItem(
                    matter_id=matter.id, matter_kind=matter.kind,
                    heading=exp, status="outstanding",
                    action_needed=(
                        f"Upload your {exp} to the Source Documents folder in the portal."
                    ),
                ))

    # Deliverables ready for client sign-off
    for d in documents:
        if d.doc_type == "deliverable":
            if d.review_status == "signed_off":
                page.items.append(LandingPageItem(
                    matter_id=matter.id, matter_kind=matter.kind,
                    heading=d.filename, status="signed_off",
                ))
            elif d.review_status in ("approved", "in_review"):
                page.items.append(LandingPageItem(
                    matter_id=matter.id, matter_kind=matter.kind,
                    heading=d.filename, status="ready_for_signoff",
                    action_needed="Please review and e-sign in the portal.",
                ))

    return page


def get_portal_backend() -> MockPortalClient:
    if os.environ.get("GRAPH_BACKEND", "mock").lower() == "graph":
        raise NotImplementedError(
            "GRAPH_BACKEND=graph requires wiring the real SharePoint external "
            "sharing API. See docs/customization.md."
        )
    return MockPortalClient()
