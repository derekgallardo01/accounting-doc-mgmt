"""CLI entrypoint: `accounting-docs <subcommand>`."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

from accounting_doc_mgmt.approval_flow import run_approval_flow, export_power_automate_json
from accounting_doc_mgmt.backend import NOW, get_backend
from accounting_doc_mgmt.copilot_index import answer_query
from accounting_doc_mgmt.matter_provisioner import MatterSpec, provision_matter
from accounting_doc_mgmt.site_definition import DEFAULT_SITE, validate_site_definition


def _list_matters(as_json: bool = False) -> None:
    b = get_backend()
    matters = b.list_matters()
    clients = {c.id: c for c in b.list_clients()}

    if as_json:
        print(json.dumps([{
            "id": m.id, "client": clients.get(m.client_id).name if clients.get(m.client_id) else "?",
            "kind": m.kind, "status": m.status,
            "due_date": m.due_date.date().isoformat(),
            "partner": m.partner_upn, "senior": m.senior_upn,
        } for m in matters], indent=2))
        return

    print(f"{'id':22s} {'client':30s} {'kind':18s} {'status':10s} {'due':10s}")
    print("-" * 96)
    for m in matters:
        client = clients.get(m.client_id)
        print(f"{m.id:22s} {(client.name if client else '?')[:29]:30s} "
              f"{m.kind:18s} {m.status:10s} {m.due_date.date()}")


def _validate_site() -> None:
    issues = validate_site_definition(DEFAULT_SITE)
    if not issues:
        print(f"Site definition valid: {DEFAULT_SITE.site_name}")
        print(f"  {len(DEFAULT_SITE.libraries)} libraries, "
              f"{len(DEFAULT_SITE.roles)} roles, "
              f"{len(DEFAULT_SITE.matter_types)} matter types")
        for lib in DEFAULT_SITE.libraries:
            print(f"  - {lib.name} - {len(lib.metadata_columns)} columns, "
                  f"retention {lib.retention_years}y")
    else:
        print("Site definition has issues:")
        for iss in issues:
            print(f"  - {iss}")


def _demo() -> None:
    print("=" * 74)
    print("ACCOUNTING DOC/PM - end-to-end demo (mock SharePoint)")
    print("=" * 74)
    print()
    print("1) List existing matters + clients")
    print("-" * 74)
    _list_matters()
    print()

    print("2) Provision a new matter (c-05 audit for 2026)")
    print("-" * 74)
    b = get_backend()
    spec = MatterSpec(
        matter_id="m-05-audit-2026",
        client_id="c-05",
        kind="audit",
        year=2026,
        partner_upn="michael.chen@acmecpas.onmicrosoft.com",
        senior_upn="emily.wong@acmecpas.onmicrosoft.com",
        staff_upns=["tyler.brooks@acmecpas.onmicrosoft.com"],
        due_date=NOW + timedelta(days=60),
    )
    result = provision_matter(spec, b)
    print(result.summary())
    print(f"  Folders created ({len(result.folders_created)}):")
    for f in result.folders_created[:6]:
        print(f"    - {f}")
    if len(result.folders_created) > 6:
        print(f"    ... plus {len(result.folders_created) - 6} more")
    print()

    print("3) Simulate a Power Automate approval flow on that matter")
    print("-" * 74)
    flow_summary = run_approval_flow(b, matter_id=spec.matter_id)
    print(flow_summary.summary())
    print()

    print("4) Answer three Copilot queries")
    print("-" * 74)
    for q in [
        "What's the status of matter m-01-tax-2026?",
        "Which matters are due in the next 30 days?",
        "Show me documents for Ridgeway Bakery that haven't been signed off",
    ]:
        ans = answer_query(q, b)
        print(f"Q: {q}")
        print(f"A [{ans.intent}]:")
        for line in ans.answer.split("\n"):
            print(f"   {line}")
        print()


def _flow_export(out_path: str | None = None) -> None:
    payload = export_power_automate_json()
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"Wrote {out_path}")
    else:
        print(json.dumps(payload, indent=2))


def _answer(query: str) -> None:
    ans = answer_query(query)
    print(f"[{ans.intent}] {ans.answer}")


def _capacity_forecast(as_json: bool = False, horizon_weeks: int = 12) -> None:
    from accounting_doc_mgmt.capacity_planner import DEFAULT_FIRM, forecast_capacity
    b = get_backend()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=horizon_weeks)

    if as_json:
        print(json.dumps({
            "summary": forecast.summary(),
            "horizon_weeks": forecast.horizon_weeks,
            "bottleneck_count": len(forecast.bottleneck_weeks),
            "hiring_suggestions": [
                {"role": h.role, "start_week": h.start_week.date().isoformat(),
                 "fte_needed": h.fte_needed, "reason": h.reason}
                for h in forecast.hiring
            ],
            "outsource_suggestions": [
                {"matter_kind": o.matter_kind, "fte_hours_needed": o.fte_hours_needed,
                 "reason": o.reason}
                for o in forecast.outsource
            ],
        }, indent=2))
        return

    print(forecast.summary())
    print()
    if forecast.bottleneck_weeks:
        print("Bottleneck weeks (demand > supply):")
        for slot in forecast.bottleneck_weeks[:10]:
            print(f"  {slot.week_start.date()}  {slot.role:20s}  "
                  f"demand={slot.demand_hours:5.0f}h  supply={slot.supply_hours:5.0f}h  "
                  f"deficit={slot.deficit():5.0f}h")
        if len(forecast.bottleneck_weeks) > 10:
            print(f"  ... plus {len(forecast.bottleneck_weeks) - 10} more")
        print()
    if forecast.hiring:
        print("Hiring suggestions:")
        for h in forecast.hiring:
            print(f"  - {h.role:20s}  start by {h.start_week.date()}  "
                  f"{h.fte_needed} FTE")
            print(f"      {h.reason}")
        print()
    if forecast.outsource:
        print("Outsource suggestions:")
        for o in forecast.outsource:
            print(f"  - {o.matter_kind:20s}  ~{o.fte_hours_needed:.0f}h to reassign")
            print(f"      {o.reason}")


def _client_portal(matter_id: str) -> None:
    from accounting_doc_mgmt.client_portal_provisioner import (
        MockPortalClient, provision_client_portal,
    )
    b = get_backend()
    matters = [m for m in b.list_matters() if m.id == matter_id]
    if not matters:
        print(f"Matter {matter_id!r} not found.")
        return
    matter = matters[0]
    docs = b.list_documents(matter_id)
    clients = {c.id: c for c in b.list_clients()}
    client = clients.get(matter.client_id)

    portal_client = MockPortalClient()
    result = provision_client_portal(
        matter=matter,
        documents=docs,
        client_email=f"contact@{client.name.lower().replace(' ', '')}.com" if client else "client@example.com",
        client_display_name=client.name if client else "Unknown client",
        portal_client=portal_client,
    )
    print(result.summary())
    print()
    for i in result.guest_invites:
        print(f"  Guest invite: {i.display_name} ({i.email}) -> matter {i.matter_id}")
    for l in result.sharing_links:
        print(f"  Sharing link: {l.library:20s}  {l.link_type:10s}  expires {l.expires_at.date()}")
    if result.warnings:
        for w in result.warnings:
            print(f"  WARNING: {w}")
    print()
    if result.landing_page:
        print("Client landing page (markdown preview):")
        print()
        for line in result.landing_page.to_markdown().split("\n"):
            print(f"    {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="accounting-docs")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_l = sub.add_parser("list-matters", help="List every matter across all clients.")
    p_l.add_argument("--json", action="store_true")

    sub.add_parser("validate-site", help="Validate the default site definition.")

    p_f = sub.add_parser("flow-export", help="Export Power Automate JSON for the approval flow.")
    p_f.add_argument("--out", type=str, default=None)

    p_q = sub.add_parser("ask", help="Ask a Copilot-style question.")
    p_q.add_argument("query", type=str)

    p_cap = sub.add_parser("capacity-forecast",
                           help="Forecast staff capacity vs demand over the next N weeks.")
    p_cap.add_argument("--horizon-weeks", type=int, default=12)
    p_cap.add_argument("--json", action="store_true")

    p_port = sub.add_parser("client-portal",
                            help="Provision the client portal for a specific matter.")
    p_port.add_argument("matter_id", type=str)

    sub.add_parser("demo", help="End-to-end walkthrough.")

    args = parser.parse_args(argv)

    if args.cmd == "list-matters":
        _list_matters(as_json=args.json)
    elif args.cmd == "validate-site":
        _validate_site()
    elif args.cmd == "flow-export":
        _flow_export(out_path=args.out)
    elif args.cmd == "ask":
        _answer(args.query)
    elif args.cmd == "capacity-forecast":
        _capacity_forecast(as_json=args.json, horizon_weeks=args.horizon_weeks)
    elif args.cmd == "client-portal":
        _client_portal(args.matter_id)
    elif args.cmd == "demo":
        _demo()
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
