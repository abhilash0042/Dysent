"""Fast tests for the newly integrated research-critical pieces."""
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from projects.shared_libs.attack_suite import sign_flip, scale, gaussian
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator
from projects.pcmi.pcmi_schema import create_pcmi, sign_pcmi, verify_pcmi


def test_attacks_change_weights():
    w=[np.ones((2,2)), np.ones(2)]
    assert np.allclose(sign_flip(w)[0], -1)
    assert np.allclose(scale(w, 3)[0], 3)
    assert not np.allclose(gaussian(w, 0.1, seed=1)[0], 1)


def test_aggregators_return_model_shape():
    updates=[[np.full((2,), i, dtype=float)] for i in range(5)]
    for fn in (
        lambda x: ByzantineRobustAggregator.median(x),
        lambda x: ByzantineRobustAggregator.trimmed_mean(x, .2),
        lambda x: ByzantineRobustAggregator.krum(x, 1),
    ):
        out=fn(updates); assert out[0].shape == (2,)


def test_pcmi_signature_gate():
    key=Ed25519PrivateKey.generate()
    pcmi=create_pcmi(victim_ip='10.0.4.10', match={'src_prefix':'10.0.1.0/24'}, action='drop', confidence=.99, collateral_est=.01, model_commit='abc', issuer_id='flA')
    sign_pcmi(pcmi, key)
    ok, reason=verify_pcmi(pcmi, key.public_key())
    assert ok and reason == 'accepted'
    pcmi.confidence=.1
    ok, reason=verify_pcmi(pcmi, key.public_key())
    assert not ok and reason == 'invalid_signature'
