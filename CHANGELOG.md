# Changelog

## [1.1.0] - 2026-07-01

### Added
- **Tax-season capacity planner** (`capacity_planner.py`) — `forecast_capacity()` projects weekly demand vs supply across the next N weeks against the current matter book, per role. Emits hiring suggestions (when a role is deficit for 2+ crunch weeks) and outsource suggestions (when one matter kind contributes 40%+ of deficit and 40+ hours). Ships `DEFAULT_EFFORT_ESTIMATES` and a `DEFAULT_FIRM` tuned to show tax-season crunch.
- **Client portal provisioner** (`client_portal_provisioner.py`) — `provision_client_portal()` produces guest invites scoped to a specific matter, two sharing links (Source Documents = edit, Deliverables = view-only), and a `LandingPage` with sections for outstanding / received / ready-for-signoff / signed-off documents. Sharing-link expiry defaults to 90 days per typical data-handling policy; longer expiries trigger warnings.
- Two new CLI subcommands: `capacity-forecast` (with `--horizon-weeks` + `--json`) and `client-portal <matter_id>`
- 20 new tests (10 capacity planner + 10 client portal) - now 58 total
- 4 new golden eval cases - now 11 total
- Extended all 6 docs to cover both new modules
- Extended live Pages demo to show capacity forecast table + client portal card with rendered landing page

## [1.0.0] - 2026-07-01

### Added
- JSON-defined SharePoint site definition + validator (4 libraries, 4 roles, 4 matter types)
- MockSharePoint backend: 10 accounting-firm clients, 19 matters, ~95 documents, permissions
- Matter provisioner (create folders + baseline docs + permissions per site definition)
- 3-step approval flow simulator (preparer -> senior -> partner) with retry + dead-letter queue
- Power Automate JSON exporter for the flow definition
- Copilot query layer with 3 intents (matter_status / due_in_days / unsigned_docs_for_client)
- CLI: `list-matters / validate-site / flow-export / ask / demo`
- End-to-end sample app: `examples/onboard_client.py` writes a client-onboarding markdown report
- 38 unit tests + 7 golden eval cases + GitHub Actions CI + Pages live demo + auto-captured screenshots
- Documented Graph swap point (msgraph-sdk + msal sketch in `docs/customization.md`)

[1.1.0]: https://github.com/derekgallardo01/accounting-doc-mgmt/releases/tag/v1.1.0
[1.0.0]: https://github.com/derekgallardo01/accounting-doc-mgmt/releases/tag/v1.0.0
