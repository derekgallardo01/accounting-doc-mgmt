"""Copilot query layer over the mock SharePoint tenant.

Answers three question shapes commonly asked in an accounting firm:

1. "What's the status of matter X?" - returns client, kind, due date,
   open documents by review status.
2. "Which matters are due in the next N days?" - returns a list of
   matters + their overdue documents.
3. "Show me documents for client X that haven't been signed off yet." -
   returns unsigned docs across every matter for that client.

Deterministic keyword-based intent classifier + structured retrieval.
Swap to a real Claude query layer via env var (sketch in
docs/customization.md).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import timedelta

from accounting_doc_mgmt.backend import Client, Document, Matter, MockSharePoint, NOW


@dataclass
class CopilotAnswer:
    intent: str
    answer: str
    matched_matters: list[Matter] = field(default_factory=list)
    matched_documents: list[Document] = field(default_factory=list)
    matched_clients: list[Client] = field(default_factory=list)


def answer_query(query: str, backend: MockSharePoint | None = None) -> CopilotAnswer:
    from accounting_doc_mgmt.backend import get_backend

    b = backend if backend is not None else get_backend()

    if os.environ.get("ACCOUNTING_LLM", "").lower() == "claude":
        return _answer_llm(query, b)

    intent = _detect_intent(query)
    if intent == "matter_status":
        return _answer_matter_status(query, b)
    if intent == "due_in_days":
        return _answer_due_in(query, b)
    if intent == "unsigned_docs_for_client":
        return _answer_unsigned_for_client(query, b)

    return CopilotAnswer(
        intent="unknown",
        answer=(
            "I can answer: 'what's the status of matter <id>?', "
            "'which matters are due in the next <N> days?', "
            "or 'show me documents for <client name> that haven't been signed off'."
        ),
    )


INTENT_KEYWORDS = {
    "matter_status": ["status of matter", "matter status", "what's the status", "how is matter"],
    "due_in_days": ["due in the next", "due this week", "due soon", "upcoming due"],
    "unsigned_docs_for_client": ["haven't been signed", "not signed off", "unsigned docs", "unfinished docs",
                                 "unsigned documents"],
}


def _detect_intent(query: str) -> str:
    q = query.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                return intent
    return "unknown"


def _answer_matter_status(query: str, backend: MockSharePoint) -> CopilotAnswer:
    match = re.search(r"m-[a-z0-9\-]+", query.lower())
    if not match:
        return CopilotAnswer(
            intent="matter_status",
            answer="I need a matter id (e.g. 'm-01-tax-2026'). Which matter?",
        )
    matter_id = match.group(0)
    matters = [m for m in backend.list_matters() if m.id == matter_id]
    if not matters:
        return CopilotAnswer(
            intent="matter_status",
            answer=f"Matter {matter_id!r} not found.",
        )
    m = matters[0]
    documents = backend.list_documents(matter_id)
    clients = {c.id: c for c in backend.list_clients()}
    client = clients.get(m.client_id)
    by_status: dict[str, int] = {}
    for d in documents:
        by_status[d.review_status] = by_status.get(d.review_status, 0) + 1
    status_line = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items()))
    ans = (
        f"Matter {m.id} - {client.name if client else 'unknown client'} - "
        f"{m.kind.replace('_', ' ')} for {m.year}. Status: {m.status}. "
        f"Due {m.due_date.date()}. Documents: {status_line or 'none uploaded yet'}. "
        f"Partner: {m.partner_upn}. Senior: {m.senior_upn}."
    )
    return CopilotAnswer(
        intent="matter_status",
        answer=ans,
        matched_matters=[m],
        matched_documents=documents,
        matched_clients=[client] if client else [],
    )


def _answer_due_in(query: str, backend: MockSharePoint) -> CopilotAnswer:
    match = re.search(r"(\d+)\s+day", query.lower())
    days = int(match.group(1)) if match else 30
    cutoff = NOW + timedelta(days=days)

    upcoming = [m for m in backend.list_matters()
                if m.status != "closed" and m.due_date <= cutoff]
    upcoming.sort(key=lambda m: m.due_date)
    clients = {c.id: c for c in backend.list_clients()}

    if not upcoming:
        return CopilotAnswer(
            intent="due_in_days",
            answer=f"No open matters are due in the next {days} days.",
        )

    ans_parts = [f"{len(upcoming)} matters due in the next {days} days:"]
    for m in upcoming[:10]:
        client = clients.get(m.client_id)
        ans_parts.append(
            f"- {m.id} ({client.name if client else '?'}) - "
            f"{m.kind.replace('_', ' ')}, due {m.due_date.date()}"
        )
    if len(upcoming) > 10:
        ans_parts.append(f"...and {len(upcoming) - 10} more.")
    return CopilotAnswer(
        intent="due_in_days",
        answer="\n".join(ans_parts),
        matched_matters=upcoming,
    )


def _answer_unsigned_for_client(query: str, backend: MockSharePoint) -> CopilotAnswer:
    clients = backend.list_clients()
    q = query.lower()
    matched_client: Client | None = None
    for c in clients:
        if c.name.lower() in q:
            matched_client = c
            break
    if matched_client is None:
        return CopilotAnswer(
            intent="unsigned_docs_for_client",
            answer=(
                "I need a client name. Try: "
                + ", ".join(c.name for c in clients[:5])
                + "..."
            ),
        )

    matters = backend.list_matters(matched_client.id)
    unsigned: list[Document] = []
    for m in matters:
        for d in backend.list_documents(m.id):
            if d.review_status != "signed_off":
                unsigned.append(d)

    if not unsigned:
        return CopilotAnswer(
            intent="unsigned_docs_for_client",
            answer=f"All documents for {matched_client.name} are signed off.",
            matched_clients=[matched_client],
        )

    ans_parts = [
        f"{len(unsigned)} unsigned documents for {matched_client.name}:"
    ]
    for d in unsigned[:10]:
        ans_parts.append(f"- {d.filename} ({d.doc_type}, status={d.review_status})")
    if len(unsigned) > 10:
        ans_parts.append(f"...and {len(unsigned) - 10} more.")
    return CopilotAnswer(
        intent="unsigned_docs_for_client",
        answer="\n".join(ans_parts),
        matched_clients=[matched_client],
        matched_documents=unsigned,
    )


def _answer_llm(query: str, backend: MockSharePoint) -> CopilotAnswer:
    """Placeholder for a real Claude query layer.

    Would issue one Claude call with a system prompt containing the
    matter + client + document tables and a JSON-schema tool for the
    query result. See docs/customization.md.
    """
    return CopilotAnswer(
        intent="llm_not_implemented",
        answer=(
            "ACCOUNTING_LLM=claude requires implementing _answer_llm. "
            "See docs/customization.md."
        ),
    )
