"""Tax-season staff capacity planner.

Every accounting firm hits the same problem in mid-January: they think
they have enough staff for the April 15 tax return deadline, then
realize on March 10 that they don't. By then it's too late to hire.

This module forecasts staff capacity per week from now to the tax
deadline (or any other due-date-clustered deadline), given:

- Current matter book (from the mock or real backend)
- Per-staff availability (hours/week) and skill (Partner / Senior / Staff)
- Per-matter-kind effort estimates (partner hours, senior hours, staff hours)

It emits a `CapacityForecast` with:

- Weekly demand vs supply per role
- Bottleneck weeks (demand > supply)
- Suggested hiring: which role, when, how many
- Suggested outsource: which matter kinds to push to a contractor

The kit deliberately errs on the side of showing the crunch early -
"you'll be 40h short in week 3" is more useful than "call in the
contractors" without a specific number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable

from accounting_doc_mgmt.backend import Matter, MockSharePoint, NOW


# Effort estimates per matter kind, in staff hours per role.
DEFAULT_EFFORT_ESTIMATES: dict[str, dict[str, float]] = {
    "tax_return":       {"Partner": 2.0,  "Senior Accountant": 6.0,  "Staff": 3.0},
    "quarterly_review": {"Partner": 0.5,  "Senior Accountant": 2.5,  "Staff": 1.5},
    "audit":            {"Partner": 8.0,  "Senior Accountant": 30.0, "Staff": 10.0},
    "advisory":         {"Partner": 4.0,  "Senior Accountant": 4.0,  "Staff": 0.0},
}


@dataclass
class Staff:
    upn: str
    display_name: str
    role: str  # "Partner" | "Senior Accountant" | "Staff"
    weekly_hours: float = 40.0


@dataclass
class WeeklySlot:
    week_start: datetime
    role: str
    demand_hours: float = 0.0
    supply_hours: float = 0.0

    def deficit(self) -> float:
        return max(0.0, self.demand_hours - self.supply_hours)

    def utilization(self) -> float:
        return self.demand_hours / self.supply_hours if self.supply_hours else 0.0


@dataclass
class HiringSuggestion:
    role: str
    start_week: datetime
    fte_needed: float  # 1.0 = one full-time equivalent
    reason: str


@dataclass
class OutsourceSuggestion:
    matter_kind: str
    fte_hours_needed: float
    reason: str


@dataclass
class CapacityForecast:
    weeks: list[WeeklySlot] = field(default_factory=list)
    bottleneck_weeks: list[WeeklySlot] = field(default_factory=list)
    hiring: list[HiringSuggestion] = field(default_factory=list)
    outsource: list[OutsourceSuggestion] = field(default_factory=list)
    horizon_weeks: int = 0

    def summary(self) -> str:
        return (
            f"Capacity forecast: {self.horizon_weeks} weeks, "
            f"{len(self.bottleneck_weeks)} bottleneck slots, "
            f"{len(self.hiring)} hiring suggestions, "
            f"{len(self.outsource)} outsource suggestions"
        )


def _week_starts(from_date: datetime, num_weeks: int) -> list[datetime]:
    # Anchor on Monday of the current week
    start = from_date - timedelta(days=from_date.weekday())
    return [start + timedelta(weeks=i) for i in range(num_weeks)]


def _in_week(matter_due: datetime, week_start: datetime) -> bool:
    return week_start <= matter_due < (week_start + timedelta(days=7))


def _effort_for_matter(matter: Matter, effort_map: dict[str, dict[str, float]]) -> dict[str, float]:
    return dict(effort_map.get(matter.kind, {}))


def forecast_capacity(
    backend: MockSharePoint,
    staff: list[Staff],
    horizon_weeks: int = 12,
    from_date: datetime | None = None,
    effort_map: dict[str, dict[str, float]] | None = None,
) -> CapacityForecast:
    """Forecast weekly capacity vs demand across the next N weeks."""
    from_date = from_date or NOW
    effort_map = effort_map or DEFAULT_EFFORT_ESTIMATES

    forecast = CapacityForecast(horizon_weeks=horizon_weeks)
    week_starts = _week_starts(from_date, horizon_weeks)
    roles = sorted({s.role for s in staff})
    supply_per_role: dict[str, float] = {}
    for role in roles:
        supply_per_role[role] = sum(s.weekly_hours for s in staff if s.role == role)

    matters = [m for m in backend.list_matters() if m.status != "closed"]

    # For each week, sum effort of matters due that week
    for week_start in week_starts:
        matters_this_week = [m for m in matters if _in_week(m.due_date, week_start)]
        for role in roles:
            demand = sum(
                _effort_for_matter(m, effort_map).get(role, 0.0)
                for m in matters_this_week
            )
            slot = WeeklySlot(
                week_start=week_start,
                role=role,
                demand_hours=demand,
                supply_hours=supply_per_role[role],
            )
            forecast.weeks.append(slot)
            if slot.deficit() > 0:
                forecast.bottleneck_weeks.append(slot)

    forecast.hiring = _suggest_hiring(forecast.bottleneck_weeks, roles)
    forecast.outsource = _suggest_outsource(forecast.bottleneck_weeks, matters,
                                            week_starts, effort_map)
    return forecast


def _suggest_hiring(bottlenecks: list[WeeklySlot], roles: Iterable[str]) -> list[HiringSuggestion]:
    """If a role is deficit for >= 2 crunch weeks (Q3 review + April tax season),
    suggest hiring. Accounting firms have exactly two annual crunch periods -
    if both are over-capacity, that's an FTE gap, not a spike."""
    per_role: dict[str, list[WeeklySlot]] = {}
    for b in bottlenecks:
        per_role.setdefault(b.role, []).append(b)

    suggestions: list[HiringSuggestion] = []
    for role, slots in per_role.items():
        if len(slots) < 2:
            continue
        peak_deficit = max(s.deficit() for s in slots)
        earliest = min(slots, key=lambda s: s.week_start).week_start
        # One FTE covers 40 hours/week
        fte_needed = peak_deficit / 40.0
        suggestions.append(HiringSuggestion(
            role=role,
            start_week=earliest - timedelta(weeks=6),  # start hiring 6 weeks before peak
            fte_needed=round(fte_needed, 1),
            reason=(
                f"{len(slots)} consecutive/near-consecutive weeks over capacity. "
                f"Peak deficit: {peak_deficit:.0f} hours in week of {slots[0].week_start.date()}."
            ),
        ))
    return suggestions


def _suggest_outsource(
    bottlenecks: list[WeeklySlot],
    matters: list[Matter],
    week_starts: list[datetime],
    effort_map: dict[str, dict[str, float]],
) -> list[OutsourceSuggestion]:
    """If a specific matter kind drives most of the deficit, suggest outsourcing it."""
    if not bottlenecks:
        return []

    # Aggregate contribution to deficits by matter kind
    contribution_by_kind: dict[str, float] = {}
    for b in bottlenecks:
        matters_in_week = [m for m in matters if _in_week(m.due_date, b.week_start)]
        for m in matters_in_week:
            eff = _effort_for_matter(m, effort_map)
            contribution_by_kind[m.kind] = (
                contribution_by_kind.get(m.kind, 0.0) + eff.get(b.role, 0.0)
            )

    total = sum(contribution_by_kind.values())
    if not total:
        return []

    suggestions: list[OutsourceSuggestion] = []
    for kind, hours in sorted(contribution_by_kind.items(), key=lambda p: -p[1]):
        share = hours / total
        if share >= 0.4 and hours >= 40:
            suggestions.append(OutsourceSuggestion(
                matter_kind=kind,
                fte_hours_needed=hours,
                reason=(
                    f"{kind!r} matters contribute {share:.0%} of total capacity "
                    f"deficit ({hours:.0f} hours). Consider outsourcing overflow."
                ),
            ))
    return suggestions


DEFAULT_FIRM = [
    # Realistic small-firm shape - a 2-partner + 1-senior + 1-staff shop.
    # Bottlenecks emerge at the Q3 review week and the April 15 crunch,
    # making the demo useful. Firms bigger than this rarely have capacity
    # problems visible from Upwork's public feed.
    Staff("sarah.jones@acmecpas.onmicrosoft.com",    "Sarah Jones",    "Partner",           30.0),
    Staff("michael.chen@acmecpas.onmicrosoft.com",   "Michael Chen",   "Partner",           30.0),
    Staff("raj.patel@acmecpas.onmicrosoft.com",      "Raj Patel",      "Senior Accountant", 40.0),
    Staff("tyler.brooks@acmecpas.onmicrosoft.com",   "Tyler Brooks",   "Staff",             40.0),
]
