"""

Misbehavior evidence records.



For every confirmed detection an evidence record is built with everything an

auditor needs (original message, expected vs observed values, AI output, trust

before/after). The SHA-256 hash of the canonical record is anchored on the

blockchain through the smart contract, so any later modification of the stored

record is detectable.

"""



import hashlib

import json

from collections import OrderedDict

from typing import Dict, List, Optional



HASHED_FIELDS = ("attack_id", "vehicle_id", "attack_type", "time", "location", "sender", "receivers",

                 "original_message", "expected", "observed", "rule_hits", "ai_probability",

                 "classification", "consensus", "trust_before", "trust_after")





def evidence_hash(record: Dict) -> str:

    payload = {k: record.get(k) for k in HASHED_FIELDS}

    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()





class EvidenceStore:

    def __init__(self, max_records: int = 3000):

        self.records: "OrderedDict[str, Dict]" = OrderedDict()

        self.by_vehicle: Dict[str, List[str]] = {}

        self.max_records = max_records

        self._seq = 1000



    def next_id(self) -> str:

        self._seq += 1

        return f"ATT-{self._seq}"



    def create(self, **fields) -> Dict:

        record = {"attack_id": self.next_id(), **fields}

        record["hash"] = evidence_hash(record)

        self.records[record["attack_id"]] = record

        self.by_vehicle.setdefault(record["vehicle_id"], []).append(record["attack_id"])

        if len(self.records) > self.max_records:

            old_id, old = self.records.popitem(last=False)

            ids = self.by_vehicle.get(old["vehicle_id"], [])

            if old_id in ids:

                ids.remove(old_id)

        return record



    def get(self, attack_id: str) -> Optional[Dict]:

        return self.records.get(attack_id)



    def for_vehicle(self, vehicle_id: str) -> List[Dict]:

        return [self.records[i] for i in self.by_vehicle.get(vehicle_id, []) if i in self.records]



    def list(self, limit: int = 100, attack_type: Optional[str] = None) -> List[Dict]:

        items = list(self.records.values())

        if attack_type:

            items = [r for r in items if r["attack_type"] == attack_type]

        return items[-limit:][::-1]
