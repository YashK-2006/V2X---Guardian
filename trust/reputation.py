import time

from dataclasses import dataclass

from typing import Dict, List, Tuple



@dataclass

class ReputationRecord:

    vehicle_id: str

    reputation_score: float

    total_observations: int

    normal_count: int

    anomaly_count: int

    last_anomaly_time: float

    created_at: float

    updated_at: float





class ReputationManager:

    def __init__(self, decay_rate: float = 0.01, window_size: int = 1000):

        self.decay_rate = decay_rate

        self.window_size = window_size

        self.reputations: Dict[str, ReputationRecord] = {}

        self.history: Dict[str, List[Tuple[float, float]]] = {}



    def update_reputation(self, vehicle_id: str, is_normal: bool, timestamp: float) -> float:

        if vehicle_id not in self.reputations:

            self._initialize_record(vehicle_id, timestamp)



        record = self.reputations[vehicle_id]



        # Apply time-based decay before update

        self.apply_decay(vehicle_id, timestamp)



        record.total_observations += 1

        record.updated_at = timestamp



        if is_normal:

            record.normal_count += 1

            # Increase reputation slightly

            record.reputation_score = min(1.0, record.reputation_score + 0.01)

        else:

            record.anomaly_count += 1

            record.last_anomaly_time = timestamp

            # Decrease reputation significantly

            record.reputation_score = max(0.0, record.reputation_score - 0.1)



        self.history[vehicle_id].append((timestamp, record.reputation_score))



        # Keep window size

        if len(self.history[vehicle_id]) > self.window_size:

            self.history[vehicle_id].pop(0)



        return record.reputation_score



    def _initialize_record(self, vehicle_id: str, timestamp: float):

        self.reputations[vehicle_id] = ReputationRecord(

            vehicle_id=vehicle_id,

            reputation_score=0.5, # Starts neutral

            total_observations=0,

            normal_count=0,

            anomaly_count=0,

            last_anomaly_time=0.0,

            created_at=timestamp,

            updated_at=timestamp

        )

        self.history[vehicle_id] = []



    def get_reputation(self, vehicle_id: str) -> ReputationRecord:

        if vehicle_id not in self.reputations:

            self._initialize_record(vehicle_id, time.time())

        return self.reputations[vehicle_id]



    def get_all_reputations(self) -> Dict[str, ReputationRecord]:

        return self.reputations



    def apply_decay(self, vehicle_id: str, current_time: float):

        if vehicle_id not in self.reputations:

            return



        record = self.reputations[vehicle_id]

        time_diff = current_time - record.updated_at



        # If considerable time has passed without anomalies, reputation slowly recovers towards 0.5 or 1.0

        # Let's say it decays towards 0.5

        if time_diff > 10.0:

            target = 0.5

            diff = target - record.reputation_score

            decay_amount = diff * self.decay_rate * (time_diff / 10.0)

            record.reputation_score += decay_amount



    def get_reputation_history(self, vehicle_id: str) -> List[Tuple[float, float]]:

        return self.history.get(vehicle_id, [])





@dataclass

class NeighborReport:

    reporter_id: str

    subject_id: str

    verdict: str          # "Normal" | "Suspicious" | "Malicious"

    reporter_trust: float

    timestamp: float





class ReportAggregator:

    """

    Aggregates misbehavior reports filed by receiving vehicles/RSUs about a sender.



    The consensus ratio is trust-weighted, so a single (possibly malicious)

    reporter cannot decide a verdict on its own, and low-trust reporters count less.

    """



    def __init__(self, window: float = 5.0, max_reports: int = 400):

        self.window = window

        self.reports: Dict[str, List[NeighborReport]] = {}

        self.max_reports = max_reports



    def submit(self, reporter_id: str, subject_id: str, verdict: str, reporter_trust: float, timestamp: float):

        lst = self.reports.setdefault(subject_id, [])

        lst.append(NeighborReport(reporter_id, subject_id, verdict, reporter_trust, timestamp))

        if len(lst) > self.max_reports:

            del lst[: len(lst) - self.max_reports]



    def consensus(self, subject_id: str, now: float) -> Dict:

        recent = [r for r in self.reports.get(subject_id, []) if now - r.timestamp <= self.window]

        latest: Dict[str, NeighborReport] = {}

        for r in recent:  # one vote per reporter (their latest)

            latest[r.reporter_id] = r

        votes = list(latest.values())

        total_w = sum(max(0.05, v.reporter_trust) for v in votes)

        mal_w = sum(max(0.05, v.reporter_trust) for v in votes if v.verdict != "Normal")

        return {

            "ratio": mal_w / total_w if total_w else 0.0,

            "reporters": len(votes),

            "flagging": sum(1 for v in votes if v.verdict != "Normal"),

            "malicious": sum(1 for v in votes if v.verdict == "Malicious"),

            "suspicious": sum(1 for v in votes if v.verdict == "Suspicious"),

            "normal": sum(1 for v in votes if v.verdict == "Normal"),

        }



    def recent_reports(self, subject_id: str, limit: int = 50) -> List[Dict]:

        return [r.__dict__ for r in self.reports.get(subject_id, [])[-limit:]]



    def forget(self, subject_id: str):

        self.reports.pop(subject_id, None)
