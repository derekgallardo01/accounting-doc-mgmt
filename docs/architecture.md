# Architecture

## Layers

```
CLI  ->  accounting_doc_mgmt.cli
              |
              v
         Analyses  ->  matter_provisioner   (provision new matter)
                       approval_flow        (3-step approval + retry + DLQ)
                       copilot_index        (3-intent query answering)
                       site_definition      (JSON schema validator)
              |
              v
         Backend  ->  MockSharePoint (in-memory) OR GraphSharePoint (msgraph-sdk sketch)
```

## The site definition

`SiteDefinition` is the shape of a SharePoint site: name, owner,
libraries, roles, matter types. Each `LibraryDefinition` has metadata
columns, default folders per matter, retention years, and optional
approval-required-for doc types.

`load_site_definition("path.json")` reads a JSON file into this
structure. `validate_site_definition(site)` returns a list of issues
(empty means valid).

## The matter provisioner

`provision_matter(spec, backend, site)` creates:

- A `Matter` record with status=open
- Folders across all 4 libraries per the site's
  `default_folders_per_matter`
- Baseline documents per matter kind (audit gets audit-plan,
  tax_return gets engagement-letter + workpaper-template, etc.)
- Permissions: Partner + Senior get write, Staff read+write, Client
  read

Returns a `ProvisionResult` with everything created + validation
issues.

## The approval flow

`run_approval_flow(backend, matter_id, decision_map)` iterates every
workpaper + deliverable in the matter and runs a 3-step approval:

1. Preparer self-review
2. Senior accountant review
3. Partner sign-off

Rejection at any step restarts the flow. After `MAX_RETRIES=2`
attempts, the document goes to `dead_lettered` state
(operationally: SharePoint DLQ list for manual triage).

`decision_map` lets tests force specific decisions per document per
step (`decision_map[doc_id][role] = ApprovalDecision.REJECT`) so the
retry / DLQ paths are exercisable.

`export_power_automate_json()` emits a JSON shape a delivery engineer
maps onto Power Automate Designer.

## The Copilot query layer

`answer_query(query, backend)` runs keyword-based intent detection and
dispatches to one of:

- `_answer_matter_status` — extracts matter id via regex, joins
  matter + client + documents
- `_answer_due_in` — extracts days via regex, filters matters by
  due_date
- `_answer_unsigned_for_client` — extracts client name via substring
  match, filters documents by review_status != signed_off

Returns a `CopilotAnswer` with:

- `intent` — the detected intent
- `answer` — human-readable answer string (multi-line for lists)
- `matched_matters` / `matched_documents` / `matched_clients` — the
  underlying objects, so the caller can render richer UIs

Setting `ACCOUNTING_LLM=claude` swaps to an LLM query layer (not yet
implemented — see `docs/customization.md`).

## The backend

`MockSharePoint` implements the full API surface:

- `list_clients()`, `list_matters(client_id=None)`,
  `list_documents(matter_id=None)`, `list_permissions(scope=None)`
- `create_matter(matter, docs, perms)`
- `update_document_status(doc_id, status, approver)`

`GraphSharePoint` is a documented sketch — see
`docs/customization.md`.
