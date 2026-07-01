# Customization

## Swap the mock SharePoint for real Graph

`MockSharePoint` defines the API surface. A production `GraphSharePoint`
is ~150 lines of `msgraph-sdk` + `msal`:

```python
from msgraph import GraphServiceClient
from msal import ConfidentialClientApplication
import os

class GraphSharePoint:
    def __init__(self, site_id: str) -> None:
        self.site_id = site_id
        self.app = ConfidentialClientApplication(
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_credential=os.environ["AZURE_CLIENT_SECRET"],
            authority=f"https://login.microsoftonline.com/{os.environ['AZURE_TENANT_ID']}",
        )
        token = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        self.client = GraphServiceClient(credentials=token["access_token"])

    def list_clients(self) -> list[Client]:
        # Read the "Clients" SharePoint list at the top of the site
        items = self.client.sites.by_site_id(self.site_id).lists.by_list_id(
            "Clients"
        ).items.get()
        return [Client(...) for item in items.value]

    def list_matters(self, client_id: str | None = None) -> list[Matter]:
        # Read the "Matters" list; filter server-side by matter's ClientId field
        ...

    def list_documents(self, matter_id: str | None = None) -> list[Document]:
        # Cross-library document search via /sites/{id}/drive/items with a
        # matter_id filter
        ...

    def list_permissions(self, scope: str | None = None) -> list[Permission]:
        # /sites/{siteId}/permissions or /sites/{siteId}/lists/{listId}/items/{id}/permissions
        ...

    def create_matter(self, matter, docs, perms) -> None:
        # POST to Matters list; POST to Deliverables + Workpapers folder-per-matter;
        # POST to permissions endpoint
        ...
```

Wire into `get_backend()`:

```python
def get_backend():
    if os.environ.get("GRAPH_BACKEND", "mock").lower() == "graph":
        return GraphSharePoint(site_id=os.environ["SHAREPOINT_SITE_ID"])
    return MockSharePoint()
```

## Deploy the Power Automate approval flow

```bash
accounting-docs flow-export --out approval-flow.json
```

Then in Power Automate Designer:

1. Create a new automated cloud flow
2. Trigger: **When an item is created or modified** (Deliverables list)
3. Add three **Send Approval** actions per the JSON structure
4. Wire the `assignee` fields to the matter's `partner_upn` / `senior_upn`
   (read from the Matters list via a lookup)
5. Configure the failure branch to send an email + set
   `review_status = 'draft'`
6. Enable **Retry policy** on the outer scope: 2 retries, 24-hour interval
7. Configure the DLQ: on final failure, add row to `Flow-DLQ` list

## Wire the Copilot layer to real Claude

Implement `_answer_llm` in `copilot_index.py`:

```python
def _answer_llm(query: str, backend: MockSharePoint) -> CopilotAnswer:
    import anthropic

    client = anthropic.Anthropic()

    # Build a compact context summary
    matters = backend.list_matters()
    clients = backend.list_clients()

    context = {
        "matters": [{"id": m.id, "client_id": m.client_id, "kind": m.kind,
                     "status": m.status, "due": m.due_date.date().isoformat()}
                    for m in matters],
        "clients": [{"id": c.id, "name": c.name} for c in clients],
    }

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "You answer accounting-firm document management questions. "
            "Given a query and structured data, produce a concise answer. "
            "Format matter IDs as `code`."
        ),
        messages=[{
            "role": "user",
            "content": f"Query: {query}\n\nContext:\n{json.dumps(context)}"
        }],
    )

    return CopilotAnswer(
        intent="llm_answer",
        answer=message.content[0].text,
    )
```

Enable with `ACCOUNTING_LLM=claude` + `ANTHROPIC_API_KEY=sk-...`.

## Add a new library to the site definition

Edit `DEFAULT_SITE` in `site_definition.py` OR write a JSON file and
load it via `load_site_definition("path.json")`. The new library will
be picked up by `validate_site_definition()`, `provision_matter()`, and
the CLI's `validate-site` command.

## Tune the capacity planner

Three sets of knobs in `capacity_planner.py`:

### Effort estimates per matter kind

```python
DEFAULT_EFFORT_ESTIMATES = {
    "tax_return":       {"Partner": 2.0,  "Senior Accountant": 6.0,  "Staff": 3.0},
    "quarterly_review": {"Partner": 0.5,  "Senior Accountant": 2.5,  "Staff": 1.5},
    "audit":            {"Partner": 8.0,  "Senior Accountant": 30.0, "Staff": 10.0},
    "advisory":         {"Partner": 4.0,  "Senior Accountant": 4.0,  "Staff": 0.0},
}
```

Bump these based on the firm's historical time-tracking data. Audit
matters vary widely — a first-year audit of a healthcare client is
much heavier than a repeat audit of a small manufacturer. Consider
adding subtypes.

### Firm composition (`DEFAULT_FIRM`)

Replace `DEFAULT_FIRM` with your actual staff. `Staff.weekly_hours`
reflects **available** hours, not paid hours — factor in vacation +
CPE + admin time.

### Hiring/outsource thresholds

- `_suggest_hiring` fires when a role has 2+ bottleneck weeks.
- `_suggest_outsource` fires when a matter kind contributes >= 40% of
  deficit AND >= 40 hours.

These are heuristics tuned for small-to-mid firms. Bigger firms may
want to raise the deficit threshold to 80 hours before recommending
outsource.

## Wire the client portal to real SharePoint external sharing

The `MockPortalClient` methods map onto the following Graph endpoints:

- `invite_guest` → `POST /invitations` (creates the B2B guest account
  + sends the redemption invitation email)
- `create_sharing_link` → `POST /sites/{siteId}/lists/{listId}/items/{id}/createLink`
  (creates the sharing link with `expirationDateTime` set)
- `revoke_sharing_link` → `DELETE /permissions/{permissionId}`

Wrap them in a `GraphPortalClient` class matching the `MockPortalClient`
interface. `provision_client_portal` is unchanged.

## Tune the client portal expiry policy

`DEFAULT_LINK_EXPIRY_DAYS = 90` in `client_portal_provisioner.py`. Some
firms' data-handling policies require 30 days; the SEC's Regulation
S-P has stricter rules for public-company clients. Adjust the constant
per client contract. The provisioner emits a warning when the requested
expiry exceeds 180 days, but doesn't refuse — the delivery lead makes
the call.

## Customize the landing page templates

`_build_landing_page()` in `client_portal_provisioner.py` hard-codes
the expected source docs per matter kind:

```python
if matter.kind == "tax_return":
    expected_source_docs = ["W-2", "1099-Div", "Prior-year return"]
```

Extend this list per client — some individuals also need Schedule K-1s,
brokerage statements, IRA distributions, etc. The "outstanding" section
of the landing page is only as useful as this list is complete.
