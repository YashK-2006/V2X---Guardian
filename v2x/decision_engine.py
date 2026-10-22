"""

V2X decision engine for trust-aware message evaluation.

"""



import sys

import time

import logging

from enum import Enum

from dataclasses import dataclass

from typing import Optional, List, Dict, Any



from config import get_config

from ai.inference import InferenceResult



logger = logging.getLogger(__name__)



class DecisionType(str, Enum):

    ACCEPT = "ACCEPT"

    VERIFY = "VERIFY"

    DOWN_WEIGHT = "DOWN_WEIGHT"

    IGNORE = "IGNORE"

    FLAG = "FLAG"



@dataclass

class MessageDecision:

    message_id: str

    vehicle_id: str

    decision: DecisionType

    trust_score: float

    ai_result: Optional[InferenceResult]

    consensus_score: float

    reason: str

    confidence: float

    timestamp: float

    processing_time_ms: float



class DecisionEngine:

    def __init__(self, config=None):

        self.config = config or get_config()

        self.decisions = []

        self.max_history = 10000



        self.stats = {

            DecisionType.ACCEPT: 0,

            DecisionType.VERIFY: 0,

            DecisionType.DOWN_WEIGHT: 0,

            DecisionType.IGNORE: 0,

            DecisionType.FLAG: 0

        }



    def evaluate_message(self, message: Any, vehicle_trust: float, ai_result: Optional[InferenceResult] = None, consensus_result: float = 1.0) -> MessageDecision:

        start_time = time.time()



        decision = DecisionType.ACCEPT

        reason = "Normal"



        # Base decision on trust thresholds from config

        t_accept = self.config.trust.trust_threshold_accept

        t_verify = self.config.trust.trust_threshold_verify

        t_downweight = self.config.trust.trust_threshold_downweight

        t_ignore = self.config.trust.trust_threshold_ignore



        if vehicle_trust >= t_accept:

            decision = DecisionType.ACCEPT

            reason = "High trust"

        elif vehicle_trust >= t_verify:

            decision = DecisionType.VERIFY

            reason = "Moderate trust"

        elif vehicle_trust >= t_downweight:

            decision = DecisionType.DOWN_WEIGHT

            reason = "Low trust"

        elif vehicle_trust >= t_ignore:

            decision = DecisionType.IGNORE

            reason = "Very low trust"

        else:

            decision = DecisionType.FLAG

            reason = "Untrusted vehicle"



        # Override with AI result

        if ai_result:

            if ai_result.severity in ['HIGH', 'CRITICAL']:

                decision = DecisionType.FLAG

                reason = f"AI detected {ai_result.severity} misbehavior"

            elif ai_result.severity == 'MEDIUM' and decision in [DecisionType.ACCEPT, DecisionType.VERIFY]:

                decision = DecisionType.DOWN_WEIGHT

                reason = "AI detected MEDIUM misbehavior"



        end_time = time.time()



        msg_id = message.get("message_id", "") if isinstance(message, dict) else getattr(message, "message_id", "")

        vid = message.get("vehicle_id", "") if isinstance(message, dict) else getattr(message, "vehicle_id", "")



        result = MessageDecision(

            message_id=msg_id,

            vehicle_id=vid,

            decision=decision,

            trust_score=vehicle_trust,

            ai_result=ai_result,

            consensus_score=consensus_result,

            reason=reason,

            confidence=ai_result.confidence if ai_result else 1.0,

            timestamp=time.time(),

            processing_time_ms=(end_time - start_time) * 1000.0

        )



        self.stats[decision] += 1

        self.decisions.append(result)

        if len(self.decisions) > self.max_history:

            self.decisions.pop(0)



        return result



    def compute_message_weight(self, trust_score: float) -> float:

        return max(0.0, min(1.0, trust_score))



    def get_decision_statistics(self) -> Dict[str, int]:

        return {k.value: v for k, v in self.stats.items()}



    def get_recent_decisions(self, count: int) -> List[MessageDecision]:

        return self.decisions[-count:] if count > 0 else []



    def get_decisions_for_vehicle(self, vehicle_id: str) -> List[MessageDecision]:

        return [d for d in self.decisions if d.vehicle_id == vehicle_id]
