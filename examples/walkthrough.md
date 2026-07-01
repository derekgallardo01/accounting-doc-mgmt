# Walkthrough: onboard_client.py

## What it does

End-to-end client-onboarding pipeline against the mock SharePoint
tenant, writing a single markdown report the practice manager can hand
to the new client on day one.

## Phases

1. **Validate the SharePoint site definition** — schema check on the
   4-library setup (Source Documents / Workpapers / Deliverables /
   Correspondence) with matter_id required on every library
2. **Provision the client + 3 matters** — tax_return / quarterly_review
   / advisory. Each matter creates folders across all 4 libraries and
   permission entries for Partner + Senior + Staff + Client
3. **Simulate the Power Automate approval flow** — 3-step
   preparer → senior → partner approval on the Q3 workpaper with
   retry + dead-letter-queue semantics
4. **Answer 3 Copilot queries** — matter status, matters due soon,
   unsigned docs for the new client

## Run

```bash
pip install -e .
python examples/onboard_client.py
```

Output: `client-onboarding-report.md` in the current directory + first
40 lines preview in the terminal.

## Wire to real SharePoint + Power Automate

The `MockSharePoint` backend defines the API surface. To point at real
SharePoint:

1. Implement `GraphSharePoint` in `backend.py` with `msgraph-sdk` +
   `msal` (see `docs/customization.md`, ~150 lines)
2. Export the approval flow JSON via `accounting-docs flow-export
   --out approval-flow.json` and import to Power Automate Designer
3. Deploy the Copilot query layer as a Copilot plugin OR as a Teams
   bot using the same `answer_query()` function

The kit's classifier + provisioner + query layer are unchanged
between mock and production.
