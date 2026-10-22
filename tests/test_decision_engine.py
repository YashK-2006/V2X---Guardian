import sys

import pytest



from v2x.decision_engine import DecisionEngine, DecisionType

from ai.inference import InferenceResult



def get_msg():

    return {"message_id": "m1", "vehicle_id": "V1"}



def test_accept_high_trust():

    engine = DecisionEngine()

    res = engine.evaluate_message(get_msg(), 0.8)

    assert res.decision == DecisionType.ACCEPT



def test_verify_medium_trust():

    engine = DecisionEngine()

    res = engine.evaluate_message(get_msg(), 0.6)

    assert res.decision == DecisionType.VERIFY



def test_ignore_low_trust():

    engine = DecisionEngine()

    res = engine.evaluate_message(get_msg(), 0.2)

    assert res.decision == DecisionType.IGNORE



def test_flag_very_low_trust():

    engine = DecisionEngine()

    res = engine.evaluate_message(get_msg(), 0.1)

    assert res.decision == DecisionType.FLAG



def test_ai_escalation():

    engine = DecisionEngine()

    ai_res = InferenceResult(

        vehicle_id="V1", label=1, confidence=0.95, anomaly_score=0.9,

        misbehavior_probability=0.9, feature_contributions={},

        model_used="test", inference_time_ms=1.0, timestamp=1000.0, severity="HIGH"

    )

    res = engine.evaluate_message(get_msg(), 0.8, ai_result=ai_res)

    assert res.decision == DecisionType.FLAG



def test_message_weight():

    engine = DecisionEngine()

    assert engine.compute_message_weight(0.5) == 0.5

    assert engine.compute_message_weight(1.5) == 1.0



def test_decision_history():

    engine = DecisionEngine()

    engine.evaluate_message(get_msg(), 0.8)

    engine.evaluate_message(get_msg(), 0.8)

    assert len(engine.get_recent_decisions(10)) == 2
