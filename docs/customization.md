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
