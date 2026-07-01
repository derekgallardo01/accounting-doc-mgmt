"""Provision a new client matter on the mock SharePoint tenant.

Given a MatterSpec + SiteDefinition, creates:
- The Matter record
- Default folders per library per the site definition
- Baseline documents where the workflow dictates
- Per-matter permissions (Partner + Senior get write, Staff read-only)

The `ProvisionResult` reports every action taken so it can be piped to a
markdown handover report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from accounting_doc_mgmt.backend import Document, Matter, MockSharePoint, Permission
from accounting_doc_mgmt.site_definition import SiteDefinition, DEFAULT_SITE, validate_site_definition


NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


@dataclass
class MatterSpec:
    matter_id: str
    client_id: str
    kind: str  # tax_return / quarterly_review / audit / advisory
    year: int
    partner_upn: str
    senior_upn: str
    staff_upns: list[str] = field(default_factory=list)
    client_reviewer_upn: str = ""
    due_date: datetime | None = None


@dataclass
class ProvisionResult:
    matter: Matter
    folders_created: list[str] = field(default_factory=list)
    documents_seeded: list[Document] = field(default_factory=list)
    permissions_set: list[Permission] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Matter {self.matter.id} provisioned: "
            f"{len(self.folders_created)} folders, "
            f"{len(self.documents_seeded)} seed docs, "
            f"{len(self.permissions_set)} permissions"
            + (f", {len(self.issues)} issue(s)" if self.issues else "")
        )


def provision_matter(
    spec: MatterSpec,
    backend: MockSharePoint,
    site: SiteDefinition | None = None,
) -> ProvisionResult:
    site = site or DEFAULT_SITE

    issues = validate_site_definition(site)

    matter = Matter(
        id=spec.matter_id,
        client_id=spec.client_id,
        kind=spec.kind,
        year=spec.year,
        status="open",
        partner_upn=spec.partner_upn,
        senior_upn=spec.senior_upn,
        due_date=spec.due_date or (NOW + timedelta(days=90)),
        opened_at=NOW,
    )

    folders: list[str] = []
    for lib in site.libraries:
        for folder in lib.default_folders_per_matter:
            folders.append(f"{lib.name}/{spec.matter_id}/{folder}")

    documents: list[Document] = _seed_documents(spec, site)

    perms: list[Permission] = [
        Permission(spec.partner_upn, "Partner",           spec.matter_id),
        Permission(spec.senior_upn,  "Senior Accountant", spec.matter_id),
    ]
    for upn in spec.staff_upns:
        perms.append(Permission(upn, "Staff", spec.matter_id))
    if spec.client_reviewer_upn:
        perms.append(Permission(spec.client_reviewer_upn, "Client", spec.matter_id))

    backend.create_matter(matter=matter, docs=documents, perms=perms)

    return ProvisionResult(
        matter=matter,
        folders_created=folders,
        documents_seeded=documents,
        permissions_set=perms,
        issues=issues,
    )


def _seed_documents(spec: MatterSpec, site: SiteDefinition) -> list[Document]:
    documents: list[Document] = []
    d_id = 0

    if spec.kind == "tax_return":
        documents.append(_make_doc(
            spec, next_id(spec, "engagement-letter.pdf", d_id := d_id + 1),
            "engagement-letter.pdf", "correspondence", "signed_off", spec.partner_upn,
        ))
        documents.append(_make_doc(
            spec, next_id(spec, "workpaper-template.xlsx", d_id := d_id + 1),
            "workpaper-template.xlsx", "workpaper", "draft", spec.senior_upn,
        ))
    elif spec.kind == "audit":
        documents.append(_make_doc(
            spec, next_id(spec, "audit-plan.docx", d_id := d_id + 1),
            "audit-plan.docx", "workpaper", "in_review", spec.senior_upn,
        ))
    elif spec.kind == "quarterly_review":
        documents.append(_make_doc(
            spec, next_id(spec, "review-checklist.xlsx", d_id := d_id + 1),
            "review-checklist.xlsx", "workpaper", "draft", spec.senior_upn,
        ))
    elif spec.kind == "advisory":
        documents.append(_make_doc(
            spec, next_id(spec, "scope-of-engagement.pdf", d_id := d_id + 1),
            "scope-of-engagement.pdf", "correspondence", "signed_off", spec.partner_upn,
        ))

    return documents


def next_id(spec: MatterSpec, filename: str, seq: int) -> str:
    return f"d-{spec.matter_id[2:]}-{seq:02d}"


def _make_doc(spec: MatterSpec, doc_id: str, filename: str, doc_type: str,
              review_status: str, uploaded_by: str) -> Document:
    approver = spec.partner_upn if review_status == "signed_off" else ""
    return Document(
        id=doc_id,
        matter_id=spec.matter_id,
        filename=filename,
        doc_type=doc_type,
        review_status=review_status,
        sensitivity="Confidential",
        uploaded_by=uploaded_by,
        uploaded_at=NOW,
        approver_upn=approver,
    )
