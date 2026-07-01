# Changelog

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

[1.0.0]: https://github.com/derekgallardo01/accounting-doc-mgmt/releases/tag/v1.0.0
