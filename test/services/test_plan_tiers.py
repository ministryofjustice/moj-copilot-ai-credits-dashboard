"""Two per-seat budget lists, because they answer two different questions.

The My Usage page and the admin weekly per-user table measure a person against
what we choose to allocate them out of the pool: $200 a month by default, $39
selectable. The pooled page sizes the pool from what GitHub actually bills per
seat, which is $39 and does not vary, so it offers that one value only.

The list is a function argument so one set of allowance maths serves both, and
so a label from the other list arriving via ?plan= cannot be honoured.
"""

from pytest import approx

from app.main.services import ai_credits as ac

POOL_ARGS = (ac.POOL_PLAN_TIERS_USD_PER_MONTH, ac.POOL_DEFAULT_PLAN)


def test_allocation_labels_lead_with_200():
    assert ac.plan_labels() == ["$200 / month", "$39 / month"]


def test_allocation_default_is_200():
    assert ac.resolve_plan(None) == "$200 / month"


def test_withdrawn_70_tier_is_not_accepted():
    assert ac.resolve_plan("$70 / month") == "$200 / month"


def test_39_is_still_selectable():
    assert ac.resolve_plan("$39 / month") == "$39 / month"


def test_weekly_allowance_for_200():
    assert ac.weekly_allowance("$200 / month") == approx(200 * 100 / 4.33)


def test_plan_limits_for_200():
    limits = ac.plan_limits("$200 / month")
    assert limits["monthly"] == approx(20000.0)
    assert limits["weekly"] == approx(200 * 100 / 4.33)
    assert limits["daily"] == approx(200 * 100 / 4.33 / 7.0)


def test_pooled_list_holds_only_the_39_we_are_billed():
    assert ac.plan_labels(ac.POOL_PLAN_TIERS_USD_PER_MONTH) == ["$39 / month"]
    assert ac.resolve_plan(None, *POOL_ARGS) == "$39 / month"
    assert ac.resolve_plan("$200 / month", *POOL_ARGS) == "$39 / month"
