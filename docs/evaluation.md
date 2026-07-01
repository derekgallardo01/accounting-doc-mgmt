# Evaluation

## Two suites

1. **Unit tests** (`tests/`) — 38 pytest tests across backend + site
   definition + matter provisioner + approval flow + Copilot index.
2. **Golden evals** (`evals/golden.json`) — 7 end-to-end cases with
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

## What the golden evals cover

1. `default_site_is_valid` — 0 issues, 4 libraries
2. `backend_has_ten_clients` — 10 clients, >= 15 matters, 5 docs per matter
3. `provision_creates_folders_across_all_libraries` — 4 library folders, >= 3 role types
4. `approval_flow_approves_default_run` — >= 1 approved, 0 DLQ
5. `copilot_answers_matter_status` — intent + client name in answer
6. `copilot_finds_due_matters` — intent + >= 1 matched matter
7. `copilot_lists_unsigned_docs` — intent + 1 matched client

## Adding a new eval

Edit `evals/golden.json`. Each case has an `op` (matching a function
in `evals/run.py::OPS`) + a list of `assertions` with `path` + one of
`eq` / `gte` / `contains`.

## CI

`.github/workflows/ci.yml` runs both suites on every push across
Python 3.10, 3.11, 3.12 and smoke-tests the CLI.
