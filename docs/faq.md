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

**Q: Do you offer this as a delivered engagement?**

Yes. See my Upwork profile at
[upwork.com/freelancers/~derekgallardo](https://www.upwork.com/freelancers/~derekgallardo)
or email derekgallardo01@gmail.com. Typical engagement: paid $175
1-hr scoping call → USD 3,500 - 5,000 fixed for the build → USD
250/mo Power Automate flow maintenance retainer.
