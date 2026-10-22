"""

Vehicle identity and pseudonym PKI.



A certificate authority (CA) enrolls every vehicle with its registered vehicle

type and issues short-lived *pseudonym certificates*: each binds a fresh

ECDSA (NIST P-256) public key and a pseudonym to the registered type, and is

signed by the CA. Vehicles sign every V2X message with the private key of their

current pseudonym certificate; receivers verify the CA signature on the

certificate and the message signature.



Only the CA (acting as misbehaviour authority) can link pseudonyms back to a

vehicle, which it does to revoke all certificates of a blacklisted vehicle

(certificate revocation list).

"""



import hashlib

import secrets

import threading

from dataclasses import dataclass, field

from typing import Dict, List, Optional



from cryptography.exceptions import InvalidSignature

from cryptography.hazmat.primitives import hashes, serialization

from cryptography.hazmat.primitives.asymmetric import ec



SIGNED_FIELDS = ("msg_id", "type", "sender_id", "cert_id", "timestamp", "nonce", "x", "y",

                 "speed", "accel", "heading", "claimed_type", "emergency_flag")

_ECDSA = ec.ECDSA(hashes.SHA256())

SIGNATURE_BYTES = 71        # typical DER-encoded P-256 signature

CERTIFICATE_BYTES = 120     # compact pseudonym certificate (explicit, ETSI-like size)





def canonical_payload(msg: Dict) -> bytes:

    parts = [f"{k}={msg.get(k)}" for k in SIGNED_FIELDS]

    event = msg.get("event")

    if event:

        parts.append(f"event={event.get('event_type')}@{event.get('x')},{event.get('y')}:{event.get('severity')}")

    return "|".join(parts).encode()





@dataclass

class PseudonymCert:

    cert_id: str

    pseudonym: str

    vehicle_id: str               # known to the CA only

    registered_type: str

    public_key: ec.EllipticCurvePublicKey

    valid_from: float

    valid_to: float

    ca_signature: bytes

    private_key: Optional[ec.EllipticCurvePrivateKey] = None   # held by the vehicle



    def tbs(self) -> bytes:

        """To-be-signed part of the certificate."""

        pub = self.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint)

        return f"{self.cert_id}|{self.pseudonym}|{self.registered_type}|{self.valid_from}|{self.valid_to}|".encode() + pub





@dataclass

class Certificate:

    """CA-side enrollment record of a vehicle (long-term identity)."""

    vehicle_id: str

    cert_id: str                  # id of the *current* pseudonym certificate

    registered_type: str

    vehicle_class: str

    pseudonym: str

    issued_at: float

    enrollment_id: str = ""

    revoked: bool = False

    revoked_at: Optional[float] = None

    revocation_reason: str = ""

    pseudonym_history: List[str] = field(default_factory=list)

    certs: List[str] = field(default_factory=list)



    def public_view(self) -> Dict:

        return {

            "vehicle_id": self.vehicle_id,

            "enrollment_id": self.enrollment_id,

            "cert_id": self.cert_id,

            "registered_type": self.registered_type,

            "vehicle_class": self.vehicle_class,

            "pseudonym": self.pseudonym,

            "issued_at": self.issued_at,

            "revoked": self.revoked,

            "revoked_at": self.revoked_at,

            "revocation_reason": self.revocation_reason,

            "pseudonym_changes": len(self.pseudonym_history),

            "pseudonym_history": self.pseudonym_history[-10:],

            "algorithm": "ECDSA P-256 / SHA-256",

        }





class IdentityRegistry:

    """Certificate authority + certificate store + CRL."""



    def __init__(self, pseudonym_lifetime: float = 60.0):

        self.pseudonym_lifetime = pseudonym_lifetime

        self._ca_key = ec.generate_private_key(ec.SECP256R1())

        self.ca_public_key = self._ca_key.public_key()

        self._by_vehicle: Dict[str, Certificate] = {}

        self._certs: Dict[str, PseudonymCert] = {}

        self._crl: set = set()

        self._cert_checked: set = set()   # certificates whose CA signature was already verified

        self._lock = threading.Lock()

        self.stats = {"signed": 0, "verified": 0, "failed": 0, "certs_issued": 0}



    @staticmethod

    def _new_pseudonym() -> str:

        return "PS-" + secrets.token_hex(4).upper()



    def _issue(self, record: Certificate, now: float) -> PseudonymCert:

        key = ec.generate_private_key(ec.SECP256R1())

        cert_id = "PC-" + secrets.token_hex(6).upper()

        pc = PseudonymCert(cert_id, self._new_pseudonym(), record.vehicle_id, record.registered_type,

                           key.public_key(), now, now + 2 * self.pseudonym_lifetime, b"", key)

        pc.ca_signature = self._ca_key.sign(pc.tbs(), _ECDSA)

        self._certs[cert_id] = pc

        record.cert_id, record.pseudonym = cert_id, pc.pseudonym

        record.certs.append(cert_id)

        self.stats["certs_issued"] += 1

        return pc



    def enroll(self, vehicle_id: str, vehicle_type: str, vehicle_class: str, now: float) -> Certificate:

        with self._lock:

            rec = self._by_vehicle.get(vehicle_id)

            if rec:

                return rec

            enrollment = "EC-" + hashlib.sha256(f"{vehicle_id}:{now}:{secrets.token_hex(4)}".encode()).hexdigest()[:12].upper()

            rec = Certificate(vehicle_id=vehicle_id, cert_id="", registered_type=vehicle_type,

                              vehicle_class=vehicle_class, pseudonym="", issued_at=now, enrollment_id=enrollment)

            self._by_vehicle[vehicle_id] = rec

            self._issue(rec, now)

            return rec



    def get(self, vehicle_id: str) -> Optional[Certificate]:

        return self._by_vehicle.get(vehicle_id)



    def by_cert(self, cert_id: str) -> Optional[Certificate]:

        pc = self._certs.get(cert_id)

        return self._by_vehicle.get(pc.vehicle_id) if pc else None



    def pseudonym_of(self, vehicle_id: str) -> Optional[str]:

        rec = self._by_vehicle.get(vehicle_id)

        return rec.pseudonym if rec else None



    def rotate_pseudonyms(self, now: float):

        with self._lock:

            for rec in self._by_vehicle.values():

                current = self._certs.get(rec.cert_id)

                if current and now - current.valid_from >= self.pseudonym_lifetime and not rec.revoked:

                    rec.pseudonym_history.append(rec.pseudonym)

                    self._issue(rec, now)



    def sign(self, vehicle_id: str, msg: Dict) -> str:

        rec = self._by_vehicle.get(vehicle_id)

        pc = self._certs.get(rec.cert_id) if rec else None

        if pc is None or pc.private_key is None:

            return ""

        self.stats["signed"] += 1

        return pc.private_key.sign(canonical_payload(msg), _ECDSA).hex()



    def verify(self, msg: Dict) -> str:

        """Returns 'valid', 'unknown_cert', 'revoked' or 'bad_signature'."""

        pc = self._certs.get(msg.get("cert_id", ""))

        if pc is None or pc.vehicle_id != msg.get("sender_id"):

            self.stats["failed"] += 1

            return "unknown_cert"

        try:

            if pc.cert_id not in self._cert_checked:

                self.ca_public_key.verify(pc.ca_signature, pc.tbs(), _ECDSA)

                self._cert_checked.add(pc.cert_id)

            pc.public_key.verify(bytes.fromhex(msg.get("signature", "")), canonical_payload(msg), _ECDSA)

        except (InvalidSignature, ValueError):

            self.stats["failed"] += 1

            return "bad_signature"

        self.stats["verified"] += 1

        if pc.cert_id in self._crl:

            return "revoked"

        return "valid"



    def revoke(self, vehicle_id: str, reason: str, now: float) -> bool:

        rec = self._by_vehicle.get(vehicle_id)

        if not rec or rec.revoked:

            return False

        rec.revoked, rec.revoked_at, rec.revocation_reason = True, now, reason

        self._crl.update(rec.certs)  # the CA links all pseudonyms of the vehicle

        return True



    def reinstate(self, vehicle_id: str, now: Optional[float] = None):

        rec = self._by_vehicle.get(vehicle_id)

        if rec:

            rec.revoked, rec.revoked_at, rec.revocation_reason = False, None, ""

            if now is not None:

                with self._lock:

                    rec.pseudonym_history.append(rec.pseudonym)

                    self._issue(rec, now)  # fresh pseudonym certificate; old ones stay on the CRL



    def revoked_list(self) -> List[Dict]:

        return [c.public_view() for c in self._by_vehicle.values() if c.revoked]



    def crl_size(self) -> int:

        return len(self._crl)



    def count(self) -> int:

        return len(self._by_vehicle)
