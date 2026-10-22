import time

import uuid

from typing import List, Optional

from .transaction import Transaction, TransactionType

from .chain import Blockchain



class SmartContract:

    def __init__(self, blockchain: Blockchain, authorized_rsus: List[str]):

        self.blockchain = blockchain

        self.authorized_rsus = authorized_rsus



    def _check_auth(self, rsu_id: str):

        if rsu_id not in self.authorized_rsus:

            raise PermissionError(f"RSU {rsu_id} is not authorized.")



    def _create_and_add_tx(self, tx_type: TransactionType, vehicle_hash: str, rsu_id: str, **kwargs) -> Transaction:

        self._check_auth(rsu_id)



        tx = Transaction(

            tx_id=str(uuid.uuid4()),

            tx_type=tx_type,

            vehicle_hash=vehicle_hash,

            timestamp=time.time(),

            reporting_rsu=rsu_id,

            data=kwargs.get('data', {}),

            event_id=kwargs.get('event_id'),

            event_type=kwargs.get('event_type'),

            misbehavior_score=kwargs.get('misbehavior_score'),

            trust_before=kwargs.get('trust_before'),

            trust_after=kwargs.get('trust_after')

        )



        # In a real system, the RSU would sign this transaction

        self.blockchain.add_transaction(tx)

        return tx



    def register_vehicle(self, vehicle_hash: str, initial_trust: float, registrar_rsu: str) -> Transaction:

        return self._create_and_add_tx(

            TransactionType.REGISTER_VEHICLE,

            vehicle_hash,

            registrar_rsu,

            trust_after=initial_trust,

            data={"initial_trust": initial_trust}

        )



    def get_vehicle_trust(self, vehicle_hash: str) -> Optional[float]:

        txs = self.blockchain.get_transactions_for_vehicle(vehicle_hash)



        # We look for the latest trust update

        latest_trust = None

        latest_time = -1



        for tx in txs:

            if tx.trust_after is not None and tx.timestamp > latest_time:

                latest_trust = tx.trust_after

                latest_time = tx.timestamp



        return latest_trust



    def record_misbehavior(self, vehicle_hash: str, event_type: str, score: float, reporter_rsu: str) -> Transaction:

        return self._create_and_add_tx(

            TransactionType.MISBEHAVIOR_REPORT,

            vehicle_hash,

            reporter_rsu,

            event_type=event_type,

            misbehavior_score=score,

            data={"reason": "Detected misbehavior"}

        )



    def update_trust(self, vehicle_hash: str, new_trust: float, old_trust: float, evidence: dict, updater_rsu: str) -> Transaction:

        return self._create_and_add_tx(

            TransactionType.TRUST_UPDATE,

            vehicle_hash,

            updater_rsu,

            trust_before=old_trust,

            trust_after=new_trust,

            data={"evidence": evidence}

        )



    def record_validation(self, vehicle_hash: str, validation_result: bool, validator_rsu: str) -> Transaction:

        return self._create_and_add_tx(

            TransactionType.VALIDATION_RECORD,

            vehicle_hash,

            validator_rsu,

            data={"result": validation_result}

        )



    def get_reputation_history(self, vehicle_hash: str) -> List[dict]:

        txs = self.blockchain.get_transactions_for_vehicle(vehicle_hash)

        history = []

        for tx in txs:

            if tx.tx_type in (TransactionType.TRUST_UPDATE, TransactionType.REGISTER_VEHICLE):

                if tx.trust_after is not None:

                    history.append({

                        "timestamp": tx.timestamp,

                        "trust_score": tx.trust_after,

                        "tx_id": tx.tx_id,

                        "type": tx.tx_type.value,

                        "rsu": tx.reporting_rsu

                    })

        # Sort by timestamp

        history.sort(key=lambda x: x["timestamp"])

        return history



    def recover_trust(self, vehicle_hash: str, new_trust: float, evidence: dict, rsu: str) -> Transaction:

        old_trust = self.get_vehicle_trust(vehicle_hash)

        if old_trust is None:

            old_trust = 0.5



        return self._create_and_add_tx(

            TransactionType.TRUST_UPDATE,

            vehicle_hash,

            rsu,

            trust_before=old_trust,

            trust_after=new_trust,

            data={"recovery": True, "evidence": evidence}

        )





def vehicle_hash(vehicle_id: str) -> str:

    """Pseudonymous on-chain identifier (no raw vehicle id is stored on-chain)."""

    import hashlib

    return hashlib.sha256(f"v2x:{vehicle_id}".encode()).hexdigest()[:24]





class TrustManagementContract:

    """

    Rule-based smart contract that automates trust decisions.



        IF misbehavior_probability > FLAG_THRESHOLD

            -> record misbehavior report + evidence hash, decrease trust, flag, notify

        ELIF misbehavior_probability > SUSPICIOUS_THRESHOLD

            -> record trust decrease (suspicious)

        IF trust < BLACKLIST_THRESHOLD           -> blacklist + revoke certificate

        IF blacklisted AND clean for probation   -> rehabilitate



    Only authorized RSUs may invoke the contract (access control).

    """



    FLAG_THRESHOLD = 0.9

    SUSPICIOUS_THRESHOLD = 0.6

    BLACKLIST_THRESHOLD = 0.15



    def __init__(self, chain, authorized_rsus: List[str]):

        self.chain = chain

        self.authorized_rsus = set(authorized_rsus)

        self.report_counts = {}

        self.evidence_index = {}

        self.blacklist = set()

        self.denied_calls = 0



    def _auth(self, rsu_id: str):

        if rsu_id not in self.authorized_rsus:

            self.denied_calls += 1

            raise PermissionError(f"{rsu_id} is not an authorized contract caller")



    def _tx(self, tx_type: TransactionType, vid: str, rsu: str, now: float, **kw) -> Transaction:

        tx = Transaction(

            tx_id="0x" + uuid.uuid4().hex[:16],

            tx_type=tx_type,

            vehicle_hash=vehicle_hash(vid),

            timestamp=now,

            reporting_rsu=rsu,

            data=kw.pop("data", {}),

            **kw,

        )

        self.chain.submit(tx, now)

        return tx



    def register_vehicle(self, vid: str, cert_id: str, registered_type: str, trust: float, rsu: str, now: float) -> Transaction:

        self._auth(rsu)

        return self._tx(TransactionType.REGISTER_VEHICLE, vid, rsu, now, trust_after=trust,

                        data={"cert_id": cert_id, "registered_type": registered_type})



    def evaluate_detection(self, vid: str, detection: dict, trust_before: float, trust_after: float,

                           rsu: str, now: float, evidence: Optional[dict] = None) -> dict:

        self._auth(rsu)

        prob = detection["probability"]

        actions, txs = [], []

        if prob > self.FLAG_THRESHOLD:

            txs.append(self._tx(TransactionType.MISBEHAVIOR_REPORT, vid, rsu, now,

                                event_type=detection["attack_type"], misbehavior_score=prob,

                                data={"classification": detection["classification"],

                                      "consensus": detection.get("consensus", 0.0)}))

            self.report_counts[vid] = self.report_counts.get(vid, 0) + 1

            if evidence:

                ev_tx = self._tx(TransactionType.EVIDENCE_RECORD, vid, rsu, now,

                                 event_id=evidence["attack_id"], event_type=detection["attack_type"],

                                 data={"evidence_hash": evidence["hash"]})

                self.evidence_index[evidence["attack_id"]] = (ev_tx.tx_id, evidence["hash"])

                txs.append(ev_tx)

            actions += ["decrease_trust", "record_evidence", "flag", "notify_network"]

        elif prob > self.SUSPICIOUS_THRESHOLD:

            actions.append("mark_suspicious")

        if prob > self.SUSPICIOUS_THRESHOLD:

            txs.append(self._tx(TransactionType.TRUST_UPDATE, vid, rsu, now, trust_before=trust_before,

                                trust_after=trust_after, event_type=detection["attack_type"],

                                misbehavior_score=prob, data={"reason": detection.get("reason", "")}))

        if trust_after < self.BLACKLIST_THRESHOLD and vid not in self.blacklist:

            self.blacklist.add(vid)

            txs.append(self._tx(TransactionType.BLACKLIST, vid, rsu, now, trust_after=trust_after,

                                event_type=detection["attack_type"], data={"revoke_certificate": True}))

            actions.append("blacklist")

        return {"actions": actions, "txs": txs}



    def rehabilitate(self, vid: str, trust_before: float, trust_after: float, rsu: str, now: float) -> Transaction:

        self._auth(rsu)

        self.blacklist.discard(vid)

        return self._tx(TransactionType.REHABILITATE, vid, rsu, now, trust_before=trust_before,

                        trust_after=trust_after, data={"probation": True})



    def record_reputation(self, vid: str, trust: float, consensus: dict, rsu: str, now: float) -> Transaction:

        self._auth(rsu)

        return self._tx(TransactionType.REPUTATION_UPDATE, vid, rsu, now, trust_after=trust,

                        data={k: consensus[k] for k in ("ratio", "reporters", "flagging")})



    def on_chain_reports(self, vid: str) -> int:

        return self.report_counts.get(vid, 0)



    def verify_evidence(self, attack_id: str, recomputed_hash: str) -> dict:

        entry = self.evidence_index.get(attack_id)

        if not entry:

            return {"on_chain": False, "valid": False}

        tx_id, stored_hash = entry

        info = self.chain.find_transaction(tx_id)

        return {"on_chain": True, "tx_id": tx_id, "confirmed": bool(info and info["confirmed"]),

                "block": info["block"] if info else None, "stored_hash": stored_hash,

                "valid": stored_hash == recomputed_hash}
