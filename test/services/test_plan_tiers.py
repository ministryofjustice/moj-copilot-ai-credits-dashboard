"""The My Usage page and the admin pages offer different per-seat budgets.

The admin pooled/weekly pages keep the $70/$39 list; the personal view uses a
$200/$39 list of its own. The tier list is an argument so one set of allowance
maths serves both, and so an admin-only label cannot be forced onto the user
page via ?plan=.
"""

from pytest import approx

from app.main.services import ai_credits as ac

USER_ARGS = (ac.USER_PLAN_TIERS_USD_PER_MONTH, ac.USER_DEFAULT_PLAN)


def test_admin_labels_unchanged_by_default():
    assert ac.plan_labels() == ["$70 / month", "$39 / month"]


def test_user_labels_lead_with_200():
    assert ac.plan_labels(ac.USER_PLAN_TIERS_USD_PER_MONTH) == [
        "$200 / month", "$39 / month"
    ]


def test_admin_default_plan_unchanged():
    assert ac.resolve_plan(None) == "$70 / month"


def test_user_default_plan_is_200():
    assert ac.resolve_plan(None, *USER_ARGS) == "$200 / month"


def test_admin_only_label_falls_back_on_the_user_side():
    assert ac.resolve_plan("$70 / month", *USER_ARGS) == "$200 / month"


def test_39_is_still_selectable_on_the_user_side():
    assert ac.resolve_plan("$39 / month", *USER_ARGS) == "$39 / month"


def test_user_weekly_allowance_for_200():
    assert ac.weekly_allowance("$200 / month", *USER_ARGS) == approx(
        200 * 100 / 4.33
    )


def test_user_plan_limits_for_200():
    limits = ac.plan_limits("$200 / month", *USER_ARGS)
    assert limits["monthly"] == approx(20000.0)
    assert limits["weekly"] == approx(200 * 100 / 4.33)
    assert limits["daily"] == approx(200 * 100 / 4.33 / 7.0)


POOL_ARGS = (ac.POOL_PLAN_TIERS_USD_PER_MONTH, ac.POOL_DEFAULT_PLAN)


def test_pooled_list_holds_only_the_39_we_are_billed():
    assert ac.plan_labels(ac.POOL_PLAN_TIERS_USD_PER_MONTH) == ["$39 / month"]
    assert ac.resolve_plan(None, *POOL_ARGS) == "$39 / month"
    assert ac.resolve_plan("$200 / month", *POOL_ARGS) == "$39 / month"
