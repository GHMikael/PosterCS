"""Tests for experiments.audit.geom_rules (objective geometric detectors)."""

from experiments.audit.geom_rules import _overlap_ratio, _is_collision


def test_overlap_ratio_intersecting():
    # b's top-left quadrant overlaps a's bottom-right; inter=50x50=2500 over min area 10000
    assert _overlap_ratio((0, 0, 100, 100), (50, 50, 100, 100)) == 0.25


def test_overlap_ratio_disjoint():
    assert _overlap_ratio((0, 0, 100, 100), (200, 200, 50, 50)) == 0.0


def test_overlap_ratio_contained_is_one():
    # small box fully inside large box → inter == smaller area → ratio 1.0
    assert _overlap_ratio((0, 0, 100, 100), (10, 10, 20, 20)) == 1.0


def test_overlap_ratio_degenerate_zero_area():
    assert _overlap_ratio((0, 0, 0, 100), (0, 0, 100, 100)) == 0.0


def test_overlap_ratio_touching_edge_not_counted():
    # share only an edge (x from 100..200), zero intersection area
    assert _overlap_ratio((0, 0, 100, 100), (100, 0, 100, 100)) == 0.0


def test_is_collision_excludes_containment():
    # small box fully inside large → ratio 1.0 → normal nesting, NOT a collision
    assert _is_collision((0, 0, 100, 100), (10, 10, 20, 20)) is False


def test_is_collision_flags_partial():
    # quarter overlap → inter/min = 0.25 → genuine partial collision
    assert _is_collision((0, 0, 100, 100), (50, 50, 100, 100)) is True


def test_is_collision_excludes_disjoint():
    assert _is_collision((0, 0, 100, 100), (200, 200, 50, 50)) is False


def test_is_collision_excludes_tiny_overlap_below_thresh():
    # overlap = 10x100 / min(100x100) = 0.10 < 0.15 thresh → not flagged
    assert _is_collision((0, 0, 100, 100), (90, 0, 100, 100)) is False
