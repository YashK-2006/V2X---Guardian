import json

import hashlib

from enum import Enum

from dataclasses import dataclass, field, asdict

from typing import Optional, Dict, Any

from ecdsa import VerifyingKey, SigningKey, SECP256k1, BadSignatureError



class TransactionType(str, Enum):

    REGISTER_VEHICLE = "REGISTER_VEHICLE"

    MISBEHAVIOR_REPORT = "MISBEHAVIOR_REPORT"

    TRUST_UPDATE = "TRUST_UPDATE"

    VALIDATION_RECORD = "VALIDATION_RECORD"

    EVIDENCE_RECORD = "EVIDENCE_RECORD"

    BLACKLIST = "BLACKLIST"

    REHABILITATE = "REHABILITATE"

    REPUTATION_UPDATE = "REPUTATION_UPDATE"



@dataclass

class Transaction:

    tx_id: str

    tx_type: TransactionType

    vehicle_hash: str

    timestamp: float

    reporting_rsu: str

    data: Dict[str, Any]

    signature: str = ""

    event_id: Optional[str] = None

    event_type: Optional[str] = None

    misbehavior_score: Optional[float] = None

    trust_before: Optional[float] = None

    trust_after: Optional[float] = None



    def to_dict(self) -> dict:

        d = asdict(self)

        d['tx_type'] = self.tx_type.value

        return d



    @classmethod

    def from_dict(cls, data: dict) -> 'Transaction':

        d = data.copy()

        d['tx_type'] = TransactionType(d['tx_type'])

        return cls(**d)



    def compute_hash(self) -> str:

        # Create a copy and remove signature before hashing

        d = self.to_dict()

        d['signature'] = ""

        block_string = json.dumps(d, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()



    def sign(self, private_key_hex: str):

        sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=SECP256k1)

        tx_hash = self.compute_hash().encode()

        sig = sk.sign(tx_hash)

        self.signature = sig.hex()



    def verify(self, public_key_hex: str) -> bool:

        if not self.signature:

            return False

        try:

            vk = VerifyingKey.from_string(bytes.fromhex(public_key_hex), curve=SECP256k1)

            tx_hash = self.compute_hash().encode()

            return vk.verify(bytes.fromhex(self.signature), tx_hash)

        except (BadSignatureError, ValueError):

            return False
