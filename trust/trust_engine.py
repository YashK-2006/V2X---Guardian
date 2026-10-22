import sys

import time

import logging

from dataclasses import dataclass

from typing import Dict, List, Optional

import math



from config import get_config, TrustConfig



logger = logging.getLogger(__name__)



@dataclass

class TrustScore:

    vehicle_id: str

    score: float

    ai_component: float

    consensus_component: float

    historical_component: float

    blockchain_component: float

    last_updated: float

    update_count: int





@dataclass

class TrustUpdate:

    vehicle_id: str

    old_score: float

    new_score: float

    reason: str

    ai_score: float

    consensus_score: float

    timestamp: float





class TrustEngine:

    def __init__(self, config: TrustConfig = None):

        self.config = config or get_config().trust

        self.alpha = self.config.alpha

        self.beta = self.config.beta

        self.gamma = self.config.gamma

        self.delta = self.config.delta



        self.trust_scores: Dict[str, TrustScore] = {}

        self.trust_history: Dict[str, List[TrustUpdate]] = {}



    def _clamp(self, value: float) -> float:

        return max(self.config.min_trust, min(self.config.max_trust, value))



    def compute_trust(self, vehicle_id: str, ai_score: float, consensus_score: float,

                      historical_reputation: float, blockchain_reputation: float) -> float:

        trust = (self.alpha * ai_score +

                 self.beta * consensus_score +

                 self.gamma * historical_reputation +

                 self.delta * blockchain_reputation)

        return self._clamp(trust)



    def update_trust(self, vehicle_id: str, ai_result: bool, consensus_result: bool) -> TrustUpdate:

        current_time = time.time()



        if vehicle_id not in self.trust_scores:

            self._initialize_vehicle(vehicle_id)



        current_score_obj = self.trust_scores[vehicle_id]

        old_score = current_score_obj.score



        # Determine change and reason based on AI and Consensus results

        # Assuming ai_result/consensus_result are True for "normal" and False for "anomaly"

        # Since the problem doesn't exactly specify the values passed for ai_result/consensus_result,

        # we will map them:

        # Both True: normal behavior

        # One False, one True: moderate anomaly

        # Both False: severe anomaly

        if ai_result and consensus_result:

            score_change = self.config.trust_increase_rate

            reason = "Normal behavior"

        elif not ai_result and not consensus_result:

            score_change = -self.config.trust_decrease_severe

            reason = "Severe anomaly / Confirmed misbehavior"

        elif ai_result and not consensus_result:

            score_change = -self.config.trust_decrease_minor

            reason = "Minor anomaly (Consensus disagreement)"

        else:

            # not ai_result and consensus_result

            score_change = -self.config.trust_decrease_moderate

            reason = "Moderate anomaly (AI detected misbehavior)"



        new_score = self._clamp(old_score + score_change)



        # In a real implementation, we would recompute the components. For simplicity, we just adjust the total score.

        ai_comp = 1.0 if ai_result else 0.0

        cons_comp = 1.0 if consensus_result else 0.0



        current_score_obj.score = new_score

        current_score_obj.last_updated = current_time

        current_score_obj.update_count += 1



        update = TrustUpdate(

            vehicle_id=vehicle_id,

            old_score=old_score,

            new_score=new_score,

            reason=reason,

            ai_score=ai_comp,

            consensus_score=cons_comp,

            timestamp=current_time

        )



        self.trust_history[vehicle_id].append(update)

        return update



    def _initialize_vehicle(self, vehicle_id: str):

        self.trust_scores[vehicle_id] = TrustScore(

            vehicle_id=vehicle_id,

            score=self.config.initial_trust,

            ai_component=self.config.initial_trust,

            consensus_component=self.config.initial_trust,

            historical_component=self.config.initial_trust,

            blockchain_component=self.config.initial_trust,

            last_updated=time.time(),

            update_count=0

        )

        self.trust_history[vehicle_id] = []



    def get_trust(self, vehicle_id: str) -> TrustScore:

        if vehicle_id not in self.trust_scores:

            self._initialize_vehicle(vehicle_id)

        return self.trust_scores[vehicle_id]



    def get_all_trusts(self) -> Dict[str, TrustScore]:

        return self.trust_scores



    def get_trust_history(self, vehicle_id: str) -> List[TrustUpdate]:

        return self.trust_history.get(vehicle_id, [])



    def recover_trust(self, vehicle_id: str):

        if not self.config.recovery_enabled:

            return



        if vehicle_id in self.trust_scores:

            current = self.trust_scores[vehicle_id]

            # Simple recovery logic: increase trust slightly if it's below initial

            if current.score < self.config.initial_trust:

                new_score = self._clamp(current.score + self.config.recovery_rate)



                update = TrustUpdate(

                    vehicle_id=vehicle_id,

                    old_score=current.score,

                    new_score=new_score,

                    reason="Trust recovery",

                    ai_score=1.0,

                    consensus_score=1.0,

                    timestamp=time.time()

                )

                current.score = new_score

                current.last_updated = time.time()

                current.update_count += 1

                self.trust_history[vehicle_id].append(update)



    def get_decision(self, trust_score: float) -> str:

        if trust_score >= self.config.trust_threshold_accept:

            return "ACCEPT"

        elif trust_score >= self.config.trust_threshold_verify:

            return "VERIFY"

        elif trust_score >= self.config.trust_threshold_downweight:

            return "DOWN_WEIGHT"

        elif trust_score >= self.config.trust_threshold_ignore:

            return "IGNORE"

        else:

            return "FLAG"



    def get_trust_distribution(self) -> dict:

        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

        histogram = {f"{bins[i]}-{bins[i+1]}": 0 for i in range(len(bins)-1)}



        for ts in self.trust_scores.values():

            score = ts.score

            for i in range(len(bins)-1):

                if bins[i] <= score <= bins[i+1]:

                    # To avoid double counting the boundaries except for 1.0

                    if i < len(bins)-2 and score == bins[i+1]:

                        continue

                    histogram[f"{bins[i]}-{bins[i+1]}"] += 1

                    break



        return histogram





ATTACK_LABELS = {

    "emergency_spoofing": "Emergency vehicle spoofing",

    "false_position": "False position",

    "gps_spoofing": "GPS spoofing",

    "false_speed": "False speed",

    "false_acceleration": "False acceleration",

    "false_heading": "False heading",

    "fake_accident": "Fake accident report",

    "message_flooding": "Message flooding",

    "replay": "Replay attack",

    "sybil": "Sybil identities",

    "message_injection": "Message injection (bad signature)",

    "revoked_identity": "Revoked certificate in use",

}





@dataclass

class TrustEvent:

    time: float

    old_score: float

    new_score: float

    reason: str

    kind: str                  # "penalty" | "reward" | "blacklist" | "rehabilitate" | "init"

    attack_type: str = ""

    probability: float = 0.0

    consensus: float = 0.0





class DynamicTrustEngine(TrustEngine):

    """

    Evidence-driven trust in [0, 1] using sim time.



    A detected misbehavior lowers trust by



        S * (alpha * p_ai + beta * consensus + gamma * history + delta * ledger)



    where p_ai is the detector probability, consensus the trust-weighted share of

    neighbours that flagged the sender, history grows with previous offences and

    ledger reflects misbehavior already recorded on the blockchain. Clean messages

    slowly restore trust; blacklisted vehicles must stay clean for

    `rehabilitation_period` seconds before being rehabilitated.

    """



    MALICIOUS_SCALE = 0.36

    SUSPICIOUS_SCALE = 0.10

    REWARD = 0.004

    PENALTY_INTERVAL = 1.0



    def __init__(self, config: TrustConfig = None, initial_trust: float = 0.9,

                 trusted_threshold: float = 0.6, malicious_threshold: float = 0.3,

                 blacklist_threshold: float = 0.15, rehabilitation_period: float = 45.0):

        super().__init__(config)

        self.initial = initial_trust

        self.trusted_threshold = trusted_threshold

        self.malicious_threshold = malicious_threshold

        self.blacklist_threshold = blacklist_threshold

        self.rehabilitation_period = rehabilitation_period

        self.scores: Dict[str, float] = {}

        self.events: Dict[str, List[TrustEvent]] = {}

        self.offences: Dict[str, int] = {}

        self.last_penalty: Dict[str, float] = {}

        self.last_offence: Dict[str, float] = {}

        self.blacklisted: Dict[str, float] = {}

        self.components: Dict[str, Dict[str, float]] = {}



    def set_weights(self, alpha: float, beta: float, gamma: float, delta: float):

        total = alpha + beta + gamma + delta

        if total <= 0:

            raise ValueError("weights must be positive")

        self.alpha, self.beta, self.gamma, self.delta = (w / total for w in (alpha, beta, gamma, delta))



    def weights(self) -> Dict[str, float]:

        return {"alpha": self.alpha, "beta": self.beta, "gamma": self.gamma, "delta": self.delta}



    def ensure(self, vid: str, now: float) -> float:

        if vid not in self.scores:

            self.scores[vid] = self.initial

            self.events[vid] = [TrustEvent(now, self.initial, self.initial, "Vehicle registered", "init")]

            self.components[vid] = {"ai": 1.0, "consensus": 1.0, "history": 1.0, "ledger": 1.0}

        return self.scores[vid]



    def score(self, vid: str) -> float:

        return self.scores.get(vid, self.initial)



    def status(self, vid: str) -> str:

        if vid in self.blacklisted:

            return "blacklisted"

        s = self.score(vid)

        if s < self.malicious_threshold:

            return "malicious"

        if s < self.trusted_threshold:

            return "suspicious"

        return "trusted"



    def _record(self, vid: str, ev: TrustEvent):

        lst = self.events.setdefault(vid, [])

        lst.append(ev)

        if len(lst) > 600:

            del lst[1:len(lst) - 599]



    def penalize(self, vid: str, now: float, probability: float, consensus: float, attack_type: str,

                 severity: str, ledger_reports: int, reporters: int = 0, flagging: int = 0) -> Optional[TrustEvent]:

        """Apply a detection. Rate-limited to one penalty per PENALTY_INTERVAL per vehicle."""

        old = self.ensure(vid, now)

        if now - self.last_penalty.get(vid, -1e9) < self.PENALTY_INTERVAL:

            return None

        self.last_penalty[vid] = now

        self.last_offence[vid] = now

        self.offences[vid] = self.offences.get(vid, 0) + 1

        history = min(1.0, (self.offences[vid] - 1) / 3.0)

        ledger = 1.0 if ledger_reports > 0 else 0.5

        scale = self.MALICIOUS_SCALE if severity == "Malicious" else self.SUSPICIOUS_SCALE

        drop = scale * (self.alpha * probability + self.beta * consensus + self.gamma * history + self.delta * ledger)

        new = self._clamp(old - drop)

        self.scores[vid] = new

        c = self.components[vid]

        c["ai"] = 0.5 * c["ai"] + 0.5 * (1 - probability)

        c["consensus"] = 0.5 * c["consensus"] + 0.5 * (1 - consensus)

        c["history"] = 1 - history

        c["ledger"] = 1 - ledger if ledger_reports else c["ledger"]

        label = ATTACK_LABELS.get(attack_type, attack_type)

        reason = f"{label} detected (p={probability:.2f}"

        if reporters:

            reason += f", {flagging}/{reporters} neighbours agree"

        reason += ")"

        ev = TrustEvent(now, old, new, reason, "penalty", attack_type, probability, consensus)

        last = self.events[vid][-1]

        if new == old and last.kind == "penalty" and last.attack_type == attack_type and last.new_score == new:

            # already at the floor: extend the previous entry instead of flooding the history

            last.time, last.reason = now, reason + " [repeated]"

            return ev

        self._record(vid, ev)

        return ev



    def reward(self, vid: str, now: float, count: int = 1) -> Optional[TrustEvent]:

        old = self.ensure(vid, now)

        if vid in self.blacklisted:

            return None

        if now - self.last_offence.get(vid, -1e9) < 5.0:

            return None  # cool-down after an offence

        new = self._clamp(old + self.REWARD * count)

        if new == old:

            return None

        self.scores[vid] = new

        c = self.components[vid]

        for k in ("ai", "consensus"):

            c[k] = min(1.0, c[k] + 0.02 * count)

        # record coarse-grained recovery steps only, to keep history readable

        last = self.events[vid][-1]

        if last.kind == "reward" and now - last.time < 5.0:

            last.new_score = new

            last.time = now

            return None

        ev = TrustEvent(now, old, new, "Consistent honest behaviour", "reward")

        self._record(vid, ev)

        return ev



    def blacklist(self, vid: str, now: float, reason: str) -> TrustEvent:

        old = self.ensure(vid, now)

        self.blacklisted[vid] = now

        ev = TrustEvent(now, old, old, f"Blacklisted: {reason}", "blacklist")

        self._record(vid, ev)

        return ev



    def rehabilitation_due(self, vid: str, now: float) -> bool:

        return vid in self.blacklisted and now - self.last_offence.get(vid, 0) >= self.rehabilitation_period



    def rehabilitate(self, vid: str, now: float, new_score: float = 0.45) -> TrustEvent:

        old = self.ensure(vid, now)

        self.blacklisted.pop(vid, None)

        self.offences[vid] = max(0, self.offences.get(vid, 0) - 2)

        self.scores[vid] = new_score

        ev = TrustEvent(now, old, new_score,

                        f"Rehabilitated after {self.rehabilitation_period:.0f}s without misbehaviour (probation)", "rehabilitate")

        self._record(vid, ev)

        return ev



    def history(self, vid: str) -> List[Dict]:

        return [e.__dict__ for e in self.events.get(vid, [])]



    def forget(self, vid: str):

        for d in (self.scores, self.events, self.offences, self.last_penalty, self.last_offence,

                  self.blacklisted, self.components):

            d.pop(vid, None)
