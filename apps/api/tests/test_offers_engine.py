"""Smoke tests for the offers engine.

These tests exercise the pure-python helpers that don't need a DB.
End-to-end POS integration is covered by the existing POS test suite.
"""



from app.services.offers_engine import (
    LOYALTY_MILESTONE,
    LOYALTY_POINT_PER_EURO,
    milestones_crossed,
    points_to_credit,
)


# ---------------------------------------------------------------------------
# Loyalty milestone helpers
# ---------------------------------------------------------------------------


def test_points_to_credit_floor_to_int_euros():
    assert points_to_credit(0) == 0
    assert points_to_credit(0.99) == 0
    assert points_to_credit(1.0) == LOYALTY_POINT_PER_EURO
    assert points_to_credit(99.99) == 99
    assert points_to_credit(100) == 100


def test_milestones_crossed_basic():
    # Customer buys 100 € for the first time → exactly 1 milestone
    assert milestones_crossed(0, 100) == 1
    # Bumping points within the same century → no milestone
    assert milestones_crossed(50, 99) == 0
    # Two milestones crossed in one go (e.g. 90 → 210)
    assert milestones_crossed(90, 210) == 2
    # No crossing if no points earned
    assert milestones_crossed(150, 150) == 0


def test_milestone_constants():
    assert LOYALTY_MILESTONE == 100
