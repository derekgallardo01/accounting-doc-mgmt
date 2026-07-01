from accounting_doc_mgmt.backend import MockSharePoint
from accounting_doc_mgmt.copilot_index import answer_query


def test_matter_status_returns_specific_matter():
    b = MockSharePoint()
    ans = answer_query("What's the status of matter m-01-tax-2026?", b)
    assert ans.intent == "matter_status"
    assert ans.matched_matters
    assert ans.matched_matters[0].id == "m-01-tax-2026"
    assert "Ridgeway Bakery" in ans.answer


def test_matter_status_reports_document_counts():
    b = MockSharePoint()
    ans = answer_query("what's the status of matter m-01-tax-2026", b)
    assert "signed_off=" in ans.answer or "in_review=" in ans.answer or "draft=" in ans.answer


def test_matter_status_unknown_matter():
    b = MockSharePoint()
    ans = answer_query("What's the status of matter m-99-fake-9999?", b)
    assert ans.intent == "matter_status"
    assert "not found" in ans.answer.lower()


def test_due_in_days_finds_upcoming():
    b = MockSharePoint()
    ans = answer_query("Which matters are due in the next 60 days?", b)
    assert ans.intent == "due_in_days"
    assert ans.matched_matters  # q3 matters are due in ~45 days


def test_due_in_days_defaults_to_30_when_missing():
    b = MockSharePoint()
    ans = answer_query("which matters are due soon?", b)
    assert ans.intent == "due_in_days"


def test_unsigned_docs_finds_client():
    b = MockSharePoint()
    ans = answer_query("Show me documents for Ridgeway Bakery that haven't been signed off", b)
    assert ans.intent == "unsigned_docs_for_client"
    assert ans.matched_clients
    assert ans.matched_clients[0].name == "Ridgeway Bakery"


def test_unsigned_docs_prompts_when_client_name_missing():
    b = MockSharePoint()
    ans = answer_query("show me unsigned documents", b)
    assert ans.intent == "unsigned_docs_for_client"
    assert "client name" in ans.answer.lower()


def test_unknown_intent_prompts_for_examples():
    b = MockSharePoint()
    ans = answer_query("What's the weather like?", b)
    assert ans.intent == "unknown"
    assert "matter" in ans.answer.lower()
