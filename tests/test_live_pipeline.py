"""

Tests for the live pipeline: identity, channel, rule detectors, trust engine,

smart contract rules, evidence anchoring and the orchestrator end to end

(with the mock traffic model so SUMO is not required).

"""



import os

import random



import pytest



from ai.misbehavior_detector import MisbehaviorDetector, FEATURE_NAMES

from ai.rule_detectors import evaluate_rules

from backend.evidence import EvidenceStore, evidence_hash

from blockchain.chain import PoABlockchain

from blockchain.smart_contract import TrustManagementContract

from simulation.attacks import AttackManager, ATTACK_TYPES

from trust.reputation import ReportAggregator

from trust.trust_engine import DynamicTrustEngine

from v2x.channel import V2XChannel

from v2x.factory import make_cam, make_denm

from v2x.identity import IdentityRegistry



RSUS = ["RSU_1", "RSU_2"]





def _state(x=100.0, y=100.0, speed=10.0, heading=90.0, vtype="car"):

    return {"position": (x, y), "speed": speed, "acceleration": 0.0, "heading": heading,

            "lane_id": "e_0", "vehicle_type": vtype}





def _features(**overrides):

    f = dict.fromkeys(FEATURE_NAMES, 0.0)

    f.update(overrides)

    return f





# ----------------------------------------------------------------- identity

def test_identity_sign_verify_and_revocation():

    reg = IdentityRegistry()

    reg.enroll("v1", "car", "passenger", 0.0)

    msg = make_cam("v1", _state(), 1.0, reg.get("v1"), random.Random(0))

    msg["signature"] = reg.sign("v1", msg)

    assert reg.verify(msg) == "valid"

    tampered = dict(msg, speed=99.0)

    assert reg.verify(tampered) == "bad_signature"

    assert reg.verify(dict(msg, cert_id="CERT-FAKE")) == "unknown_cert"

    reg.revoke("v1", "test", 2.0)

    assert reg.verify(msg) == "revoked"





# ------------------------------------------------------------------ channel

def test_channel_delivers_only_within_range():

    ch = V2XChannel(v2v_range=300, rsu_range=500, base_loss=0.0, seed=1)

    ch.update_topology({"a": (0, 0), "b": (100, 0), "c": (1000, 0)}, [{"id": "R", "x": 0, "y": 400}])

    deliveries = {d.receiver_id: d for d in ch.broadcast("a", (0, 0))}

    assert "b" in deliveries and deliveries["b"].channel == "V2V"

    assert "c" not in deliveries

    assert deliveries["R"].channel == "V2I"

    assert all(d.latency_ms > 0 for d in deliveries.values())





# ------------------------------------------------------------ rule detectors

def test_rule_emergency_spoofing():

    hits = evaluate_rules(_features(claimed_emergency=1, type_mismatch=1),

                          {"registered_type": "car", "claimed_type": "ambulance"})

    assert hits[0].attack_type == "emergency_spoofing" and hits[0].score >= 0.95

    assert "car" in hits[0].expected and "ambulance" in hits[0].observed





def test_rule_replay_and_sybil_and_injection():

    assert evaluate_rules(_features(duplicate_nonce=1), {})[0].attack_type == "replay"

    sybil = evaluate_rules(_features(unknown_cert=1, colocated_ids=2), {})

    assert sybil[0].attack_type == "sybil"

    assert evaluate_rules(_features(bad_signature=1), {})[0].attack_type == "message_injection"





def test_rule_legit_emergency_vehicle_not_flagged():

    assert evaluate_rules(_features(claimed_emergency=1, registered_emergency=1, event_emergency=1, is_denm=1),

                          {"registered_type": "ambulance", "claimed_type": "ambulance"}) == []





def test_detector_flags_spoofed_cam_end_to_end():

    reg = IdentityRegistry()

    reg.enroll("v1", "car", "passenger", 0.0)

    det = MisbehaviorDetector(reg)  # rules only

    rng = random.Random(0)

    msg = make_cam("v1", _state(), 1.0, reg.get("v1"), rng)

    msg["claimed_type"], msg["emergency_flag"] = "ambulance", True

    msg["signature"] = reg.sign("v1", msg)

    res = det.detect_batch([(msg, (100.0, 100.0))], 1.0)[0]

    assert res["classification"] == "Malicious"

    assert res["attack_type"] == "emergency_spoofing"

    honest = make_cam("v1", _state(x=110), 2.0, reg.get("v1"), rng)

    honest["signature"] = reg.sign("v1", honest)

    assert det.detect_batch([(honest, (110.0, 100.0))], 2.0)[0]["classification"] == "Normal"





def test_attack_manager_replay_reuses_captured_message():

    am = AttackManager(seed=1)

    reg = IdentityRegistry()

    for v in ("victim", "attacker"):

        reg.enroll(v, "car", "passenger", 0.0)

    rng = random.Random(0)

    victim_msg = make_cam("victim", _state(), 1.0, reg.get("victim"), rng)

    am.transform(victim_msg, _state(), 1.0, reg.sign)

    am.capture(victim_msg)

    am.launch("attacker", "replay", 1.0)

    out = am.transform(make_cam("attacker", _state(x=300), 6.0, reg.get("attacker"), rng), _state(x=300), 6.0, reg.sign)

    replayed = [m for m in out if m["_attack"] == "replay"]

    assert replayed and replayed[0]["nonce"] == victim_msg["nonce"] and replayed[0]["_tx"] == "attacker"





# ---------------------------------------------------------- trust / reputation

def test_dynamic_trust_penalty_blacklist_and_rehabilitation():

    t = DynamicTrustEngine(initial_trust=0.9, rehabilitation_period=10)

    t.ensure("v", 0.0)

    first = t.penalize("v", 1.0, 0.97, 1.0, "emergency_spoofing", "Malicious", 0)

    assert first.new_score < 0.9 and "Emergency vehicle spoofing" in first.reason

    assert t.penalize("v", 1.5, 0.97, 1.0, "emergency_spoofing", "Malicious", 1) is None  # rate limited

    for i in range(2, 6):

        t.penalize("v", float(i), 0.97, 1.0, "emergency_spoofing", "Malicious", 1)

    assert t.status("v") == "malicious"

    t.blacklist("v", 6.0, "test")

    assert t.status("v") == "blacklisted"

    assert not t.rehabilitation_due("v", 8.0)

    assert t.rehabilitation_due("v", 20.0)

    t.rehabilitate("v", 20.0)

    assert t.status("v") == "suspicious"





def test_report_aggregator_is_trust_weighted():

    agg = ReportAggregator(window=5)

    agg.submit("honest1", "x", "Malicious", 0.9, 1.0)

    agg.submit("honest2", "x", "Malicious", 0.9, 1.0)

    agg.submit("liar", "x", "Normal", 0.1, 1.0)

    c = agg.consensus("x", 2.0)

    assert c["reporters"] == 3 and c["flagging"] == 2 and c["ratio"] > 0.9





# ------------------------------------------------- smart contract / evidence

def test_contract_rules_and_evidence_verification():

    chain = PoABlockchain(RSUS, block_interval=1.0)

    contract = TrustManagementContract(chain, RSUS)

    store = EvidenceStore()

    ev = store.create(vehicle_id="v", attack_type="emergency_spoofing", time=1.0, location=[0, 0], sender="v",

                      receivers=3, original_message={}, expected="car", observed="ambulance", rule_hits=[],

                      ai_probability=0.97, classification="Malicious", consensus=1.0, trust_before=0.9, trust_after=0.1)

    out = contract.evaluate_detection("v", {"probability": 0.97, "attack_type": "emergency_spoofing",

                                            "classification": "Malicious"}, 0.9, 0.1, "RSU_1", 1.0, ev)

    assert {"flag", "record_evidence", "notify_network", "blacklist"} <= set(out["actions"])

    assert contract.on_chain_reports("v") == 1

    block = chain.seal(3.0)

    assert block is not None and chain.verify_block_signature(block) and chain.validate_chain()

    assert contract.verify_evidence(ev["attack_id"], evidence_hash(ev))["valid"]

    tampered = dict(ev, ai_probability=0.1)

    assert not contract.verify_evidence(ev["attack_id"], evidence_hash(tampered))["valid"]

    with pytest.raises(PermissionError):

        contract.register_vehicle("v2", "c", "car", 0.9, "EVIL_RSU", 1.0)





def test_poa_round_robin_validators():

    chain = PoABlockchain(RSUS, block_interval=1.0)

    contract = TrustManagementContract(chain, RSUS)

    validators = []

    for i in range(4):

        contract.register_vehicle(f"v{i}", "c", "car", 0.9, "RSU_1", float(i * 2))

        validators.append(chain.seal(float(i * 2 + 1)).validator)

    assert validators == ["RSU_1", "RSU_2", "RSU_1", "RSU_2"]





# ------------------------------------------------------ orchestrator (mock)

@pytest.fixture

def orchestrator(monkeypatch):

    monkeypatch.setenv("V2X_MOCK_TRAFFIC", "1")

    monkeypatch.setenv("V2X_PERSIST_RUNS", "0")

    from config import get_config

    from backend.orchestrator import SimulationOrchestrator

    o = SimulationOrchestrator(get_config())

    o.setup("normal")

    o.start()

    yield o

    o.shutdown()





def test_orchestrator_emergency_spoofing_demo_flow(orchestrator):

    o = orchestrator

    for _ in range(50):

        o.step()

    attack = o.launch_attack(None, "emergency_spoofing")

    vid = attack["vehicle_id"]

    for _ in range(80):

        o.step()

    comp = o.attack_comparison(vid)

    assert comp["first_detection"] is not None

    assert comp["after"]["trust"] < 0.3 and comp["after"]["status"] in ("malicious", "blacklisted")

    assert comp["evidence_ids"], "evidence should be recorded on-chain"

    alerts = [a for a in o.alerts if a["kind"] == "emergency_spoofing"]

    assert alerts and alerts[0]["details"]["claimed_type"] != alerts[0]["details"]["actual_type"]



    # a neighbour's received history shows the spoofed messages with verdicts

    receivers = [r for r in o.received if any(rec[0]["sender"] == vid for rec in o.received[r])]

    assert receivers

    hist = o.received_messages(receivers[0], "malicious", sender=vid)

    assert hist["messages"] and hist["messages"][0]["attack_type"] == "emergency_spoofing"

    assert all(m["classification"] == "Normal" for m in o.received_messages(receivers[0], "valid")["messages"])





def test_orchestrator_all_attacks_detected_without_false_blacklisting(orchestrator):

    o = orchestrator

    for _ in range(50):

        o.step()

    attackers = {}

    for attack in ATTACK_TYPES:

        attackers[o.launch_attack(None, attack)["vehicle_id"]] = attack

    for _ in range(300):

        o.step()

    sec = o.get_stats()["security"]

    assert sec["detection_rate"] > 0.9

    assert sec["false_positive_rate"] < 0.01

    attackers = set(o.attack_reports)  # includes every member of the collusion group

    innocent_blacklisted = [v for v in o.trust.blacklisted if v not in attackers]

    assert not innocent_blacklisted





def test_orchestrator_collusion_v2p_notifications_and_privacy(orchestrator):

    o = orchestrator

    for _ in range(50):

        o.step()

    attack = o.launch_attack(None, "collusion")

    members = attack["params"]["members"]

    assert len(members) >= 2

    for _ in range(150):

        o.step()

    assert o.per_attack["collusion"]["detected"] > 0

    assert all(o.trust.status(m) in ("malicious", "blacklisted") for m in members)

    comm = o.get_stats()["communication"]

    assert comm["v2p"] > 0 and comm["pedestrians"] > 0

    assert comm["i2v_notifications"] > 0

    receiver = next(v for v in o.received if any(r[0]["type"] == "MBR" for r in o.received[v]))

    plain = o.received_messages(receiver, mtype="MBR", limit=1)["messages"][0]

    masked = o.received_messages(receiver, mtype="MBR", limit=1, privacy=True)["messages"][0]

    assert plain["subject"] in members and masked["subject"].startswith("PS-")

    assert o.replay_frames() and "v" in o.replay_frames()[0]

    perf = o.get_performance()

    assert perf["security_impact"]["malicious_delivered"] > 0

    assert perf["v2x"]["latency_p95_ms"] >= perf["v2x"]["latency_p50_ms"] > 0





def test_centralized_ledger_misses_tampering():

    from blockchain.chain import CentralizedLedger

    for chain, expected in ((PoABlockchain(RSUS, block_interval=0.0), False), (CentralizedLedger(), True)):

        contract = TrustManagementContract(chain, RSUS)

        contract.register_vehicle("v", "c", "car", 0.9, "RSU_1", 1.0)

        chain.seal(2.0)

        chain.chain[1].transactions[0].data["registered_type"] = "ambulance"

        assert chain.validate_chain() is expected
