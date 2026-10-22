import sys

import pytest

import numpy as np



from simulation.vehicle_manager import VehicleManager, VehicleState

from v2x.message import V2XMessage, MessageType

from ai.feature_extractor import FeatureExtractor

from ai.inference import InferenceEngine, InferenceResult

from trust.consensus import NeighborConsensus

from trust.trust_engine import TrustEngine

from blockchain.chain import Blockchain

from blockchain.smart_contract import SmartContract

from v2x.decision_engine import DecisionEngine, DecisionType

from blockchain.transaction import TransactionType



class MockSupervisedModel:

    def __init__(self):

        self.is_fitted = True

    def predict_single(self, features):

        if features[0] > 0:

            return (1, 0.9, {})

        return (0, 0.9, {})



def test_complete_pipeline():

    manager = VehicleManager()

    v_ids = [f"V{i}" for i in range(10)]

    for vid in v_ids:

        manager.register_vehicle(vid)

    manager.assign_behavior_types(v_ids, 0.1)



    misbehaving_list = manager.get_vehicles_by_type("misbehaving")

    assert len(misbehaving_list) == 1

    v_bad = misbehaving_list[0].identity.vehicle_id



    v_good = [vid for vid in v_ids if vid != v_bad][0]



    msg_bad = V2XMessage(

        vehicle_id=v_bad, vehicle_hash="h_bad", latitude=0, longitude=0,

        position_x=500.0, position_y=0.0, speed=50.0, acceleration=0.0,

        heading=0.0, lane_id="", message_type=MessageType.CAM

    )



    gt_bad = {"position": (10.0, 0.0), "speed": 15.0, "acceleration": 0.0, "heading": 0.0}



    ext = FeatureExtractor()

    feat_bad = ext.extract_features(v_bad, msg_bad, None, [], {}, gt_bad)

    arr_bad = ext.to_numpy(feat_bad)



    ai = InferenceEngine()

    ai.supervised_model = MockSupervisedModel()

    ai_res = ai.infer_single(v_bad, arr_bad)



    consensus = NeighborConsensus()

    cons_res = consensus.compute_consensus(v_bad, msg_bad.to_dict(), [], {})



    trust_engine = TrustEngine()

    ai_status = ai_res.label == 0

    cons_status = cons_res.consensus_score >= 0.5

    trust_engine.update_trust(v_bad, ai_status, cons_status)

    trust_score = trust_engine.get_trust(v_bad).score



    bc = Blockchain()

    sc = SmartContract(bc, ["RSU1"])

    sc.register_vehicle("h_bad", 0.5, "RSU1")

    sc.record_misbehavior("h_bad", "SPEEDING", ai_res.misbehavior_probability, "RSU1")

    bc.mine_block("RSU1")



    de = DecisionEngine()

    decision_res = de.evaluate_message(msg_bad, trust_score, ai_res, cons_res.consensus_score)



    assert ai_res.label == 1

    assert trust_score < 0.5

    assert decision_res.decision == DecisionType.FLAG

    assert len(bc.get_transactions_for_vehicle("h_bad")) == 2
