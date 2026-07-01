# Architecture

## Layers

```
CLI  ->  accounting_doc_mgmt.cli
              |
              v
         Analyses  ->  matter_provisioner         (provision new matter)
                       approval_flow              (3-step approval + retry + DLQ)
                       copilot_index              (3-intent query answering)
                       site_definition            (JSON schema validator)
                       capacity_planner           (weekly demand vs supply + hiring/outsource)
                       client_portal_provisioner  (guest access + expiring links + landing page)
              |
              v
         Backend  ->  MockSharePoint (in-memory) OR GraphSharePoint (msgraph-sdk sketch)
                      MockPortalClient (for the portal provisioner seam)
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

## The capacity planner

`forecast_capacity(backend, staff, horizon_weeks)` returns a
`CapacityForecast` with:

- **Weekly demand vs supply per role** — sums effort of matters due
  each week from `DEFAULT_EFFORT_ESTIMATES` per matter kind
- **Bottleneck weeks** — every `WeeklySlot` where `demand > supply`
- **Hiring suggestions** — if a role is deficit for >= 2 weeks
  (accounting firms have exactly 2 annual crunch periods; both being
  over-capacity means an FTE gap, not a spike). Suggests role,
  start-by date (6 weeks before earliest crunch), and FTE count
- **Outsource suggestions** — if one matter kind contributes >= 40%
  of total deficit AND >= 40 hours, suggest pushing it to a contractor

Per-role effort estimates per matter kind are tunable in
`DEFAULT_EFFORT_ESTIMATES`:

```python
"tax_return":       {"Partner": 2.0,  "Senior Accountant": 6.0,  "Staff": 3.0}
"quarterly_review": {"Partner": 0.5,  "Senior Accountant": 2.5,  "Staff": 1.5}
"audit":            {"Partner": 8.0,  "Senior Accountant": 30.0, "Staff": 10.0}
"advisory":         {"Partner": 4.0,  "Senior Accountant": 4.0,  "Staff": 0.0}
```

`DEFAULT_FIRM` ships a realistic small-firm shape (2 partners at 30h/week
+ 1 senior + 1 staff) so the demo shows crunch when tax season hits.

## The client portal provisioner

`provision_client_portal(matter, documents, client_email,
client_display_name, portal_client, link_expiry_days)` returns a
`ProvisioningResult` with:

- **Guest invite** — client contact scoped to the specific matter
  (not the whole site)
- **Two sharing links** — Source Documents (edit, so client can
  upload) and Deliverables (view-only, so client can only see final)
- **Sharing link expiry** — defaults to 90 days per typical
  data-handling policy; longer expiries trigger a warning
- **Landing page** — a `LandingPage` object with per-status items:
  outstanding (what the client owes us), received (being reviewed),
  ready_for_signoff (needs client e-sign), signed_off (done)

`LandingPage.to_markdown()` renders sections in the order the client
cares about: "Please provide" first, then sign-off, then received,
then completed.

The `MockPortalClient` is the seam. `revoke_sharing_link()` is
supported so the portal can be closed cleanly at engagement end.
