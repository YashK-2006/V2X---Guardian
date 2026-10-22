import sys

import pytest



from trust.consensus import NeighborConsensus



def test_full_agreement():

    consensus = NeighborConsensus()

    target_msg = {"event_type": "ACCIDENT"}

    neighbors = [{"vehicle_id": "V1", "event_type": "ACCIDENT"}, {"vehicle_id": "V2", "event_type": "ACCIDENT"}]

    scores = {"V1": 1.0, "V2": 1.0}

    res = consensus.compute_consensus("V_TARGET", target_msg, neighbors, scores)

    assert res.consensus_score == 1.0



def test_full_disagreement():

    consensus = NeighborConsensus()

    target_msg = {"event_type": "ACCIDENT"}

    neighbors = [{"vehicle_id": "V1", "event_type": "CLEAR"}, {"vehicle_id": "V2", "event_type": "CLEAR"}]

    scores = {"V1": 1.0, "V2": 1.0}

    res = consensus.compute_consensus("V_TARGET", target_msg, neighbors, scores)

    assert res.consensus_score == 0.0



def test_partial_agreement():

    consensus = NeighborConsensus()

    target_msg = {"event_type": "ACCIDENT"}

    neighbors = [{"vehicle_id": "V1", "event_type": "ACCIDENT"}, {"vehicle_id": "V2", "event_type": "CLEAR"}]

    scores = {"V1": 1.0, "V2": 1.0}

    res = consensus.compute_consensus("V_TARGET", target_msg, neighbors, scores)

    assert res.consensus_score == 0.5



def test_trust_weighted_consensus():

    consensus = NeighborConsensus()

    target_msg = {"event_type": "ACCIDENT"}

    neighbors = [{"vehicle_id": "V1", "event_type": "ACCIDENT"}, {"vehicle_id": "V2", "event_type": "CLEAR"}]

    scores = {"V1": 0.8, "V2": 0.2}

    res = consensus.compute_consensus("V_TARGET", target_msg, neighbors, scores)

    assert res.consensus_score == 0.8



def test_no_neighbors():

    consensus = NeighborConsensus()

    res = consensus.compute_consensus("V_TARGET", {}, [], {})

    assert res.consensus_score == 0.5
