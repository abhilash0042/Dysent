"""Clipping, stronger aggregators, and the attacks that can slip past a median."""
import numpy as np

from projects.shared_libs.attack_suite import adaptive_update, apply_weight_attack, gaussian
from projects.shared_libs.byzantine_defense import (
    AggregationUnsupported,
    ByzantineRobustAggregator,
    aggregate_updates,
    clip_update,
    update_l2,
)
from experiments.federated_learning.run_byzantine_improved import run_trial


def _honest(scale=0.1):
    return [[np.full(8, scale), np.array([scale])]]


def test_clip_bounds_a_gaussian_update():
    poisoned = gaussian(_honest(0.01)[0], std=1e6, seed=0)
    clipped = clip_update(poisoned, 1.0)
    assert update_l2(clipped) <= 1.0 + 1e-6
    assert np.isfinite(np.concatenate([w.ravel() for w in clipped])).all()


def test_unclipped_average_explodes_and_clip_keeps_it_finite():
    honest = _honest(0.01) * 8
    poisoned = [apply_weight_attack(_honest(0.01)[0], "gaussian", seed=1, std=1e6)] * 2
    raw = ByzantineRobustAggregator.fedavg(honest + poisoned)
    assert update_l2(raw) > 1000
    safe = aggregate_updates(honest + poisoned, "fedavg_clip", clip_norm=1.0)
    assert np.isfinite(safe[0]).all()
    assert update_l2(safe) < 2


def test_krum_refuses_when_too_many_are_byzantine():
    updates = _honest() * 5
    try:
        ByzantineRobustAggregator.krum(updates, num_byzantine=4)
        raised = False
    except AggregationUnsupported:
        raised = True
    assert raised


def test_multi_krum_prefers_the_honest_cluster():
    honest = [[np.full(4, 0.2)]] * 7
    poisoned = [[np.full(4, -5.0)]] * 3
    mixed = aggregate_updates(honest + poisoned, "multi_krum", num_byzantine=3, clip_norm=10.0)
    assert mixed[0].mean() > 0


def test_bulyan_shape_and_limit():
    updates = [[np.full(3, i * 0.01)] for i in range(11)]
    out = aggregate_updates(updates, "bulyan", num_byzantine=2, clip_norm=10.0)
    assert out[0].shape == (3,)
    try:
        aggregate_updates(updates, "bulyan", num_byzantine=3, clip_norm=10.0)
        refused = False
    except AggregationUnsupported:
        refused = True
    assert refused


def test_trust_weighted_downweights_the_outlier():
    updates = [[np.ones(4)]] * 6 + [[np.full(4, 100.0)]]
    mixed = aggregate_updates(updates, "trust_weighted", clip_norm=1000.0)
    assert mixed[0].mean() < 5


def test_median_resists_sign_flip_better_than_fedavg():
    fed = run_trial(40, "sign_flip", "fedavg", seed=0, clients=12, rounds=4, n_train=1500, n_test=400)
    med = run_trial(40, "sign_flip", "median", seed=0, clients=12, rounds=4, n_train=1500, n_test=400)
    assert fed["status"] == "success" and med["status"] == "success"
    assert med["f1"] > fed["f1"]


def test_adaptive_stays_closer_than_sign_flip():
    honest = [[np.full(6, 0.2) + np.random.default_rng(i).normal(0, 0.01, 6)] for i in range(5)]
    near = adaptive_update(honest, bias=3.0)
    flipped = apply_weight_attack(honest[0], "sign_flip")
    mean = np.mean(np.stack([h[0] for h in honest]), axis=0)
    near_dist = np.linalg.norm(near[0] - mean)
    flip_dist = np.linalg.norm(flipped[0] - mean)
    assert near_dist < flip_dist


def test_gaussian_with_clip_stays_finite():
    row = run_trial(40, "gaussian", "fedavg_clip", seed=1, clients=10, rounds=3, n_train=800, n_test=200)
    assert row["status"] == "success"
    assert np.isfinite(row["f1"])
