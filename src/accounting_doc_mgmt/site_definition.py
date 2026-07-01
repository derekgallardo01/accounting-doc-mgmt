"""JSON-defined SharePoint site definition.

The accounting firm defines their whole site (libraries, metadata columns,
default folders per matter type, permissions) in a single JSON file. The
kit reads that file, validates it, and provisions the site.

This is the pattern from `sharepoint-intranet-generator` scaled DOWN to
just a client-matter document management system, plus retention +
approval-flow wiring at the library level.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MetadataColumn:
    name: str
    type: str  # "text" | "choice" | "date" | "user"
    required: bool = False
    choices: list[str] = field(default_factory=list)


@dataclass
class LibraryDefinition:
    name: str
    description: str = ""
    metadata_columns: list[MetadataColumn] = field(default_factory=list)
    default_folders_per_matter: list[str] = field(default_factory=list)
    retention_years: int = 7
    approval_required_for: list[str] = field(default_factory=list)  # doc_types


@dataclass
class RoleDefinition:
    name: str
    permissions: list[str] = field(default_factory=list)  # "read" | "write" | "approve" | "admin"


@dataclass
class SiteDefinition:
    site_name: str
    site_owner_upn: str
    libraries: list[LibraryDefinition] = field(default_factory=list)
    roles: list[RoleDefinition] = field(default_factory=list)
    matter_types: list[str] = field(default_factory=list)

    def get_library(self, name: str) -> LibraryDefinition | None:
        for lib in self.libraries:
            if lib.name == name:
                return lib
        return None


DEFAULT_SITE = SiteDefinition(
    site_name="Client Files",
    site_owner_upn="admin@acmecpas.onmicrosoft.com",
    libraries=[
        LibraryDefinition(
            name="Source Documents",
            description="Client-provided source materials (W-2s, 1099s, receipts).",
            metadata_columns=[
                MetadataColumn("matter_id", "text", required=True),
                MetadataColumn("doc_type", "choice", required=True,
                               choices=["W-2", "1099", "K-1", "receipt", "statement", "other"]),
                MetadataColumn("tax_year", "text", required=True),
                MetadataColumn("received_from_client", "date", required=True),
            ],
            default_folders_per_matter=["Received", "Client-Portal-Upload"],
            retention_years=7,
        ),
        LibraryDefinition(
            name="Workpapers",
            description="Internal workpapers, spreadsheets, memos.",
            metadata_columns=[
                MetadataColumn("matter_id", "text", required=True),
                MetadataColumn("review_status", "choice", required=True,
                               choices=["draft", "in_review", "approved", "signed_off"]),
                MetadataColumn("preparer", "user", required=True),
                MetadataColumn("reviewer", "user"),
            ],
            default_folders_per_matter=["Working Papers", "Reviewed", "Signed Off"],
            retention_years=7,
            approval_required_for=["workpaper", "deliverable"],
        ),
        LibraryDefinition(
            name="Deliverables",
            description="Signed returns, audited financials, advisory memos.",
            metadata_columns=[
                MetadataColumn("matter_id", "text", required=True),
                MetadataColumn("doc_type", "choice", required=True,
                               choices=["tax_return", "audit_report", "advisory_memo", "management_letter"]),
                MetadataColumn("final_partner_signoff", "user"),
                MetadataColumn("delivered_to_client_at", "date"),
            ],
            default_folders_per_matter=["Draft", "Final"],
            retention_years=7,
            approval_required_for=["tax_return", "audit_report"],
        ),
        LibraryDefinition(
            name="Correspondence",
            description="Client emails, notes, phone-log entries.",
            metadata_columns=[
                MetadataColumn("matter_id", "text", required=True),
                MetadataColumn("author", "user", required=True),
                MetadataColumn("communication_type", "choice",
                               choices=["email", "phone_log", "note", "meeting_minutes"]),
            ],
            default_folders_per_matter=["General"],
            retention_years=3,
        ),
    ],
    roles=[
        RoleDefinition("Partner", permissions=["read", "write", "approve", "admin"]),
        RoleDefinition("Senior Accountant", permissions=["read", "write", "approve"]),
        RoleDefinition("Staff", permissions=["read", "write"]),
        RoleDefinition("Client", permissions=["read"]),
    ],
    matter_types=["tax_return", "quarterly_review", "audit", "advisory"],
)


def load_site_definition(path: str | Path) -> SiteDefinition:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return SiteDefinition(
        site_name=data["site_name"],
        site_owner_upn=data["site_owner_upn"],
        matter_types=data.get("matter_types", []),
        libraries=[
            LibraryDefinition(
                name=lib["name"],
                description=lib.get("description", ""),
                metadata_columns=[
                    MetadataColumn(
                        name=col["name"],
                        type=col["type"],
                        required=col.get("required", False),
                        choices=col.get("choices", []),
                    )
                    for col in lib.get("metadata_columns", [])
                ],
                default_folders_per_matter=lib.get("default_folders_per_matter", []),
                retention_years=lib.get("retention_years", 7),
                approval_required_for=lib.get("approval_required_for", []),
            )
            for lib in data.get("libraries", [])
        ],
        roles=[
            RoleDefinition(name=r["name"], permissions=r.get("permissions", []))
            for r in data.get("roles", [])
        ],
    )


def validate_site_definition(site: SiteDefinition) -> list[str]:
    """Return a list of issues; empty means valid."""
    issues: list[str] = []
    if not site.site_name:
        issues.append("site_name is required")
    if not site.site_owner_upn:
        issues.append("site_owner_upn is required")
    if not site.libraries:
        issues.append("at least one library is required")

    library_names = [lib.name for lib in site.libraries]
    if len(library_names) != len(set(library_names)):
        issues.append("library names must be unique")

    for lib in site.libraries:
        if not lib.metadata_columns:
            issues.append(f"library {lib.name!r} has no metadata columns")
        required_cols = [c for c in lib.metadata_columns if c.required]
        if not any(c.name == "matter_id" for c in required_cols):
            issues.append(f"library {lib.name!r} must include a required 'matter_id' column")

    return issues
