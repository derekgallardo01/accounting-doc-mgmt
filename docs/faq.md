# FAQ

**Q: Do you need Power Automate premium?**

For the built-in Send Approval action + SharePoint triggers, no — a
seeded M365 Business Standard plan covers it. The Power Automate JSON
this kit exports uses only standard connectors. If you extend the
flow with the HTTP action (to call an external system on approval),
you'd need Premium.

---

**Q: Can I use this without SharePoint? We're on OneDrive shared
folders.**

No. The kit's data model assumes SharePoint libraries + list-based
metadata columns. OneDrive shared folders don't have per-item
metadata, so the query layer + approval flow have nothing to route
on. If you're on OneDrive, adopt SharePoint first (2-3 day migration)
before wiring this kit.

---

**Q: The mock has 10 clients + 19 matters. Will it scale to my firm's
   500 clients?**

Yes — nothing in the kit is O(n^2). The heaviest operation is the
Copilot query layer's due-in-days scan, which is O(n) over matters.
At 500 clients × ~5 matters each = 2500 matters, that scan runs in
<10ms in-memory. Against real Graph, the bottleneck is Graph API
paging (100 items per call) — plan on 30-40 sec for a full
5000-item enumeration. Cache in a SharePoint list for the query layer.

---

**Q: How do I add a new matter type (e.g. "estate_planning")?**

Add "estate_planning" to `SiteDefinition.matter_types` (or the JSON
equivalent). Add a `_seed_documents` branch in `matter_provisioner.py`
that seeds the estate-planning-specific baseline docs. Add golden
cases + pytest cases. That's it — the approval flow and Copilot query
layer work unchanged.

---

**Q: The approval flow simulator says "dead_lettered" — what happens
   in production?**

In the exported Power Automate JSON, `dead_letter_queue:
"sharepoint_list://Flow-DLQ"` means: create a SharePoint list called
`Flow-DLQ` in your site, and configure the flow's outermost scope's
error handler to add a row to that list containing the failing item's
matter_id, doc_id, and error message. Someone on your team watches
that list weekly.

---

**Q: Does the Copilot query layer work with Microsoft Copilot Chat?**

Not directly. The `answer_query()` function is the query layer — how
you expose it depends on your Copilot deployment. Two options:

1. **Custom Copilot plugin** — wrap `answer_query` in a Copilot
   Studio plugin. Copilot Chat can then invoke it as a tool.
2. **Teams bot** — deploy the function behind a Teams bot; users
   type `/matter-status m-01-tax-2026` and get an answer inline.

Both are ~2-3 days of integration work on top of this kit.

---

**Q: When should I actually run the capacity forecast? What's the
timing?**

Run it three times a year:

- **January**, after the client roster is set for the year. This is
  the "do I need to hire for tax season?" run. If it fires a
  HiringSuggestion, you have ~10 weeks to recruit before the April 15
  crunch.
- **June**, before Q3 review season. Same shape, different deadline.
- **On matter add** — every time you add a big matter (a new audit
  client, a large advisory engagement), re-run to see if it broke
  next quarter's capacity.

Running it hourly is overkill — matter counts and staff availability
don't change that fast.

---

**Q: The capacity planner says "0 bottlenecks" but I'm sure we're
overloaded. What's wrong?**

Two things to check:

1. Are the effort estimates in `DEFAULT_EFFORT_ESTIMATES` too low for
   your firm? A tax return at 6 senior hours is fast; if your firm
   actually spends 12 hours per return, double the estimate.
2. Is `Staff.weekly_hours` measuring paid hours instead of billable?
   Partners paid for 40 hours often only have 25 billable — the rest
   is admin, sales, CPE. Set `weekly_hours` to billable-only.

Retune, re-run; bottlenecks emerge.

---

**Q: Can the client portal share with multiple client contacts, not
just one?**

Yes, though `provision_client_portal()` takes one email. Call it once
per contact — the `MockPortalClient` accumulates invites + links
across calls. In production, ensure your Graph portal client
deduplicates guest accounts with the same email.

---

**Q: What happens when a sharing link expires? Does the client just
lose access silently?**

Yes — that's SharePoint's default. In production, add a scheduled job
that runs weekly and checks
`portal_client.list_links(include_revoked=False)` for links expiring
within 14 days, then emails the delivery lead. The kit doesn't ship
this job (depends on your notification stack: Teams / Outlook /
Slack), but the primitive is there.

---

**Q: Do you offer this as a delivered engagement?**

Yes. See my Upwork profile at
[upwork.com/freelancers/~derekgallardo](https://www.upwork.com/freelancers/~derekgallardo)
or email derekgallardo01@gmail.com. Typical engagement: paid $175
1-hr scoping call → USD 3,500 - 5,000 fixed for the build → USD
250/mo Power Automate flow maintenance retainer + capacity forecast
runs per season.
