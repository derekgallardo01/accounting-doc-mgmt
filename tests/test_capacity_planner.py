from datetime import datetime, timedelta, timezone

from accounting_doc_mgmt.backend import MockSharePoint, NOW
from accounting_doc_mgmt.capacity_planner import (
    DEFAULT_EFFORT_ESTIMATES,
    DEFAULT_FIRM,
    Staff,
    forecast_capacity,
)


def test_default_firm_has_all_three_roles():
    roles = {s.role for s in DEFAULT_FIRM}
    assert roles == {"Partner", "Senior Accountant", "Staff"}


def test_default_effort_estimates_cover_all_kinds():
    kinds = set(DEFAULT_EFFORT_ESTIMATES.keys())
    assert kinds == {"tax_return", "quarterly_review", "audit", "advisory"}


def test_forecast_produces_weekly_slots():
    b = MockSharePoint()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=8)
    # 8 weeks x 3 roles = 24 slots
    assert len(forecast.weeks) == 24
    assert forecast.horizon_weeks == 8


def test_supply_matches_staff_hours():
    b = MockSharePoint()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=4)
    partner_slots = [s for s in forecast.weeks if s.role == "Partner"]
    # 2 partners * 30 hrs
    for slot in partner_slots:
        assert slot.supply_hours == 60.0


def test_deficit_zero_when_no_matters_due():
    """Weeks with no matters due should have zero demand."""
    b = MockSharePoint()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=52)
    zero_demand = [s for s in forecast.weeks if s.demand_hours == 0]
    assert zero_demand


def test_deficit_flagged_when_demand_exceeds_supply():
    """Simulate an under-staffed firm - just Sarah - to force deficits."""
    b = MockSharePoint()
    tiny_firm = [Staff("a@x.com", "A", "Senior Accountant", 5.0)]
    forecast = forecast_capacity(b, staff=tiny_firm, horizon_weeks=52)
    assert forecast.bottleneck_weeks
    for slot in forecast.bottleneck_weeks:
        assert slot.deficit() > 0


def test_hiring_suggested_when_multiple_bottleneck_weeks():
    b = MockSharePoint()
    tiny_firm = [Staff("a@x.com", "A", "Senior Accountant", 2.0)]
    forecast = forecast_capacity(b, staff=tiny_firm, horizon_weeks=52)
    assert forecast.hiring
    assert any(h.role == "Senior Accountant" for h in forecast.hiring)


def test_hiring_reason_mentions_deficit():
    b = MockSharePoint()
    tiny_firm = [Staff("a@x.com", "A", "Senior Accountant", 2.0)]
    forecast = forecast_capacity(b, staff=tiny_firm, horizon_weeks=52)
    for h in forecast.hiring:
        assert "deficit" in h.reason.lower() or "over capacity" in h.reason.lower()


def test_outsource_suggested_when_kind_dominates_deficit():
    b = MockSharePoint()
    tiny_firm = [Staff("a@x.com", "A", "Senior Accountant", 2.0)]
    forecast = forecast_capacity(b, staff=tiny_firm, horizon_weeks=52)
    if forecast.outsource:
        # If any outsource suggestions are made, they should be for a real kind
        for o in forecast.outsource:
            assert o.matter_kind in DEFAULT_EFFORT_ESTIMATES


def test_healthy_firm_has_no_bottlenecks():
    b = MockSharePoint()
    huge_firm = [
        Staff("a@x.com", "A", "Partner", 200.0),
        Staff("b@x.com", "B", "Senior Accountant", 400.0),
        Staff("c@x.com", "C", "Staff", 200.0),
    ]
    forecast = forecast_capacity(b, staff=huge_firm, horizon_weeks=12)
    assert not forecast.bottleneck_weeks
    assert not forecast.hiring
    assert not forecast.outsource


def test_summary_format():
    b = MockSharePoint()
    forecast = forecast_capacity(b, staff=DEFAULT_FIRM, horizon_weeks=12)
    s = forecast.summary()
    assert "weeks" in s
    assert "bottleneck" in s
    assert "hiring" in s
    assert "outsource" in s
