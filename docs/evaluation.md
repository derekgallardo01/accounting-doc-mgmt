# Evaluation

## Two suites

1. **Unit tests** (`tests/`) — 58 pytest tests across backend + site
   definition + matter provisioner + approval flow + Copilot index +
   capacity planner + client portal provisioner.
2. **Golden evals** (`evals/golden.json`) — 11 end-to-end cases with
   path-based assertions.

## What the pytest suite covers

- **Backend (9 tests):** 10 clients, 3 kinds, matters per client,
  documents seeded per matter, permissions per role, `create_matter`
  appends, `update_document_status` mutates
- **Site definition (7 tests):** default is valid, 4 libraries,
  matter_id required, Deliverables approvals configured, JSON
  roundtrip, validation catches missing owner / duplicate libs /
  missing matter_id
- **Matter provisioner (7 tests):** creates in backend, folders across
  all libraries, all roles set, staff added, kind-appropriate seeds,
  summary formatted, client reviewer optional
- **Approval flow (6 tests):** default run approves, partner reject
  → rejected, max retries → dead-lettered, abstain, summary format,
  export JSON shape
- **Copilot index (9 tests):** matter status returns matter, includes
  doc counts, unknown matter → not-found, due-in-days finds upcoming,
  default 30 when missing, unsigned finds client, prompts when
  missing client, unknown intent prompts for examples
- **Capacity planner (10 tests):** default firm has all 3 roles,
  effort estimates cover all kinds, forecast produces weekly slots,
  supply matches staff hours, deficit=0 when no matters due, deficit
  flagged when demand>supply, hiring suggested at 2+ bottleneck weeks,
  reason mentions deficit, outsource suggested for kind dominance,
  huge firm has no bottlenecks
- **Client portal provisioner (10 tests):** creates guest invite,
  creates two sharing links, Source Documents is edit + Deliverables
  is view-only, default expiry matches config, long expiry triggers
  warning, landing page flags missing source docs, markdown renders
  sections, revoke_sharing_link works, summary includes counts

## What the golden evals cover

11 end-to-end cases:

1. `default_site_is_valid` — 0 issues, 4 libraries
2. `backend_has_ten_clients` — 10 clients, >= 15 matters, 5 docs per matter
3. `provision_creates_folders_across_all_libraries` — 4 library folders, >= 3 role types
4. `approval_flow_approves_default_run` — >= 1 approved, 0 DLQ
5. `copilot_answers_matter_status` — intent + client name in answer
6. `copilot_finds_due_matters` — intent + >= 1 matched matter
7. `copilot_lists_unsigned_docs` — intent + 1 matched client
8. `capacity_planner_finds_tax_season_crunch` — default firm produces >= 1 bottleneck + >= 1 outsource suggestion over 52-week horizon
9. `capacity_planner_no_bottleneck_for_huge_firm` — over-staffed firm produces 0 bottlenecks + 0 hiring suggestions
10. `client_portal_provisions_invite_and_links` — 1 invite + 2 links (Source edit / Deliverables view-only)
11. `client_portal_landing_page_flags_outstanding` — >= 1 outstanding item + "Please provide" section in markdown

## Adding a new eval

Edit `evals/golden.json`. Each case has an `op` (matching a function
in `evals/run.py::OPS`) + a list of `assertions` with `path` + one of
`eq` / `gte` / `contains`.

## CI

`.github/workflows/ci.yml` runs both suites on every push across
Python 3.10, 3.11, 3.12 and smoke-tests every CLI subcommand
including `capacity-forecast` and `client-portal`.
