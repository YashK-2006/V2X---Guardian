import sys

import pytest



from trust.trust_engine import TrustEngine



def test_initial_trust():

    engine = TrustEngine()

    score = engine.get_trust("V1")

    assert score.score == engine.config.initial_trust



def test_trust_increase_normal():

    engine = TrustEngine()

    engine.update_trust("V1", True, True)

    assert engine.get_trust("V1").score > engine.config.initial_trust



def test_trust_decrease_misbehavior():

    engine = TrustEngine()

    engine.update_trust("V1", False, False)

    assert engine.get_trust("V1").score < engine.config.initial_trust



def test_trust_bounds():

    engine = TrustEngine()

    for _ in range(100):

        engine.update_trust("V1", True, True)

    assert engine.get_trust("V1").score <= engine.config.max_trust

    for _ in range(100):

        engine.update_trust("V2", False, False)

    assert engine.get_trust("V2").score >= engine.config.min_trust



def test_trust_recovery():

    engine = TrustEngine()

    engine.update_trust("V1", False, False)

    low_score = engine.get_trust("V1").score

    engine.recover_trust("V1")

    assert engine.get_trust("V1").score > low_score



def test_trust_weights():

    engine = TrustEngine()

    trust = engine.compute_trust("V1", 1.0, 1.0, 1.0, 1.0)

    assert trust == 1.0



def test_trust_decision_thresholds():

    engine = TrustEngine()

    assert engine.get_decision(0.8) == "ACCEPT"

    assert engine.get_decision(0.6) == "VERIFY"

    assert engine.get_decision(0.2) == "IGNORE"

    assert engine.get_decision(0.1) == "FLAG"
