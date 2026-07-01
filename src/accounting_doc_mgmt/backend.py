"""Mock SharePoint tenant modeling an accounting firm.

Ships:
- 10 clients (Small business + individual + a couple of partnerships)
- ~40 matters (2026 tax return, quarterly review, audit, etc.)
- ~200 documents spanning source docs (W-2, 1099), workpapers, deliverables
- Metadata columns: matter_id, doc_type, review_status, sensitivity
- 3 site roles: Partner, Senior Accountant, Staff

Set GRAPH_BACKEND=graph to swap to real SharePoint via msgraph-sdk.
Sketch in docs/customization.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


@dataclass
class Client:
    id: str
    name: str
    kind: str  # "individual" | "small_business" | "partnership"
    industry: str = ""
    partner_upn: str = ""


@dataclass
class Matter:
    id: str
    client_id: str
    kind: str  # "tax_return" | "quarterly_review" | "audit" | "advisory"
    year: int
    status: str  # "open" | "in_review" | "signed_off" | "closed"
    partner_upn: str
    senior_upn: str
    due_date: datetime
    opened_at: datetime


@dataclass
class Document:
    id: str
    matter_id: str
    filename: str
    doc_type: str  # "source" | "workpaper" | "deliverable" | "correspondence"
    review_status: str  # "draft" | "in_review" | "approved" | "signed_off"
    sensitivity: str  # "Internal" | "Confidential" | "Highly Confidential"
    uploaded_by: str
    uploaded_at: datetime
    approver_upn: str = ""


@dataclass
class Permission:
    principal_upn: str
    role: str  # "Partner" | "Senior Accountant" | "Staff" | "Client"
    scope: str  # matter_id or "site"


PARTNER_A = "sarah.jones@acmecpas.onmicrosoft.com"
PARTNER_B = "michael.chen@acmecpas.onmicrosoft.com"
SENIOR_A = "raj.patel@acmecpas.onmicrosoft.com"
SENIOR_B = "emily.wong@acmecpas.onmicrosoft.com"
STAFF_A = "tyler.brooks@acmecpas.onmicrosoft.com"


class MockSharePoint:
    """Deterministic in-memory SharePoint tenant."""

    def __init__(self) -> None:
        self._clients = self._build_clients()
        self._matters = self._build_matters()
        self._documents = self._build_documents()
        self._permissions = self._build_permissions()
        self._provisioned_matter_ids: set[str] = set()

    def list_clients(self) -> list[Client]:
        return list(self._clients)

    def list_matters(self, client_id: str | None = None) -> list[Matter]:
        if client_id is None:
            return list(self._matters)
        return [m for m in self._matters if m.client_id == client_id]

    def list_documents(self, matter_id: str | None = None) -> list[Document]:
        if matter_id is None:
            return list(self._documents)
        return [d for d in self._documents if d.matter_id == matter_id]

    def list_permissions(self, scope: str | None = None) -> list[Permission]:
        if scope is None:
            return list(self._permissions)
        return [p for p in self._permissions if p.scope == scope]

    def create_matter(self, matter: Matter, docs: list[Document] = None,
                      perms: list[Permission] = None) -> None:
        self._matters.append(matter)
        if docs:
            self._documents.extend(docs)
        if perms:
            self._permissions.extend(perms)
        self._provisioned_matter_ids.add(matter.id)

    def update_document_status(self, doc_id: str, status: str, approver: str = "") -> None:
        for d in self._documents:
            if d.id == doc_id:
                d.review_status = status
                if approver:
                    d.approver_upn = approver
                return

    def _build_clients(self) -> list[Client]:
        return [
            Client("c-01", "Ridgeway Bakery",           "small_business", "food",         PARTNER_A),
            Client("c-02", "Bluewater Marine LLC",      "small_business", "marine",       PARTNER_A),
            Client("c-03", "Cortez Family Dentistry",   "small_business", "healthcare",   PARTNER_A),
            Client("c-04", "Delaney & Sons Contracting","partnership",    "construction", PARTNER_A),
            Client("c-05", "Ellis Photography Studio",  "small_business", "creative",     PARTNER_B),
            Client("c-06", "Franklin Tax Services",     "partnership",    "professional_services", PARTNER_B),
            Client("c-07", "Greta Simmons",             "individual",     "individual",   PARTNER_B),
            Client("c-08", "Hayworth Consulting",       "small_business", "consulting",   PARTNER_B),
            Client("c-09", "Iyer Digital Agency",       "small_business", "marketing",    PARTNER_B),
            Client("c-10", "Junction Coffee Roasters",  "small_business", "food",         PARTNER_B),
        ]

    def _build_matters(self) -> list[Matter]:
        matters: list[Matter] = []
        due_apr = datetime(2027, 4, 15, tzinfo=timezone.utc)
        due_q3 = NOW + timedelta(days=45)
        opened_2026 = NOW - timedelta(days=90)
        opened_q3 = NOW - timedelta(days=20)

        for i, client in enumerate(self._build_clients()):
            senior = SENIOR_A if i % 2 == 0 else SENIOR_B
            matters.append(Matter(
                id=f"m-{client.id[2:]}-tax-2026",
                client_id=client.id,
                kind="tax_return",
                year=2026,
                status="in_review" if i % 3 == 0 else "open",
                partner_upn=client.partner_upn,
                senior_upn=senior,
                due_date=due_apr,
                opened_at=opened_2026,
            ))
            if client.kind != "individual":
                matters.append(Matter(
                    id=f"m-{client.id[2:]}-q3-2026",
                    client_id=client.id,
                    kind="quarterly_review",
                    year=2026,
                    status="open",
                    partner_upn=client.partner_upn,
                    senior_upn=senior,
                    due_date=due_q3,
                    opened_at=opened_q3,
                ))
        return matters

    def _build_documents(self) -> list[Document]:
        docs: list[Document] = []
        d_id = 0

        for matter in self._build_matters():
            base = [
                (f"{matter.year}-W2.pdf",         "source",       "signed_off"),
                (f"{matter.year}-1099-Div.pdf",   "source",       "signed_off"),
                (f"{matter.year}-source-summary.xlsx", "workpaper", "in_review"),
                (f"{matter.year}-return-draft.pdf",    "deliverable", "draft"),
                (f"correspondence-client-{matter.year}Q1.msg", "correspondence", "signed_off"),
            ]
            for filename, doc_type, status in base:
                d_id += 1
                docs.append(Document(
                    id=f"d-{d_id:04d}",
                    matter_id=matter.id,
                    filename=filename,
                    doc_type=doc_type,
                    review_status=status,
                    sensitivity="Confidential",
                    uploaded_by=matter.senior_upn if doc_type != "correspondence" else matter.partner_upn,
                    uploaded_at=matter.opened_at + timedelta(days=2),
                    approver_upn=matter.partner_upn if status == "signed_off" else "",
                ))
        return docs

    def _build_permissions(self) -> list[Permission]:
        perms: list[Permission] = [
            Permission(PARTNER_A, "Partner",           "site"),
            Permission(PARTNER_B, "Partner",           "site"),
            Permission(SENIOR_A,  "Senior Accountant", "site"),
            Permission(SENIOR_B,  "Senior Accountant", "site"),
            Permission(STAFF_A,   "Staff",             "site"),
        ]
        return perms


class GraphSharePoint:
    """Sketch of the production SharePoint backend using msgraph-sdk.

    See docs/customization.md.
    """

    def __init__(self) -> None:  # pragma: no cover - documentation only
        raise NotImplementedError(
            "GraphSharePoint requires msgraph-sdk. See docs/customization.md."
        )


def get_backend() -> MockSharePoint | GraphSharePoint:
    if os.environ.get("GRAPH_BACKEND", "mock").lower() == "graph":
        return GraphSharePoint()
    return MockSharePoint()
