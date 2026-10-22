import time

import json

from collections import deque

import hashlib

from dataclasses import dataclass, field, asdict

from typing import List, Dict, Optional

import sys



from config import get_config

from .transaction import Transaction



@dataclass

class Block:

    index: int

    timestamp: float

    transactions: List[Transaction]

    previous_hash: str

    nonce: int

    hash: str

    validator: str

    merkle_root: str



    def to_dict(self):

        return {

            'index': self.index,

            'timestamp': self.timestamp,

            'transactions': [tx.to_dict() for tx in self.transactions],

            'previous_hash': self.previous_hash,

            'nonce': self.nonce,

            'hash': self.hash,

            'validator': self.validator,

            'merkle_root': self.merkle_root

        }



    @classmethod

    def from_dict(cls, data: dict) -> 'Block':

        d = data.copy()

        d['transactions'] = [Transaction.from_dict(tx_data) for tx_data in d['transactions']]

        return cls(**d)



    def compute_merkle_root(self) -> str:

        if not self.transactions:

            return ""



        hashes = [tx.compute_hash() for tx in self.transactions]



        while len(hashes) > 1:

            if len(hashes) % 2 != 0:

                hashes.append(hashes[-1])

            new_hashes = []

            for i in range(0, len(hashes), 2):

                combined = (hashes[i] + hashes[i+1]).encode()

                new_hashes.append(hashlib.sha256(combined).hexdigest())

            hashes = new_hashes



        return hashes[0]



    def compute_hash(self) -> str:

        self.merkle_root = self.compute_merkle_root()

        block_content = {

            'index': self.index,

            'timestamp': self.timestamp,

            'previous_hash': self.previous_hash,

            'nonce': self.nonce,

            'validator': self.validator,

            'merkle_root': self.merkle_root

        }

        block_string = json.dumps(block_content, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest()





class Blockchain:

    def __init__(self, config=None):

        self.config = config or get_config().blockchain

        self.chain: List[Block] = []

        self.pending_transactions: List[Transaction] = []



        # Create genesis block

        self._create_genesis_block()



    def _create_genesis_block(self):

        genesis_block = Block(

            index=0,

            timestamp=0.0, # fixed for genesis

            transactions=[],

            previous_hash="0",

            nonce=0,

            hash="",

            validator="genesis",

            merkle_root=""

        )

        genesis_block.hash = genesis_block.compute_hash()

        self.chain.append(genesis_block)



    def add_transaction(self, transaction: Transaction):

        if len(self.pending_transactions) < self.config.max_pending_transactions:

            self.pending_transactions.append(transaction)



    def mine_block(self, validator_id: str, timestamp: Optional[float] = None) -> Optional[Block]:

        if not self.pending_transactions:

            return None



        # Get up to block_size transactions

        txs_to_mine = self.pending_transactions[:self.config.block_size]



        last_block = self.get_latest_block()

        new_block = Block(

            index=last_block.index + 1,

            timestamp=time.time() if timestamp is None else timestamp,

            transactions=txs_to_mine,

            previous_hash=last_block.hash,

            nonce=0,

            hash="",

            validator=validator_id,

            merkle_root=""

        )



        # Simple PoA: no complex proof of work needed, just hash it

        new_block.hash = new_block.compute_hash()



        self.chain.append(new_block)



        # Remove mined transactions

        self.pending_transactions = self.pending_transactions[len(txs_to_mine):]



        return new_block



    def get_latest_block(self) -> Block:

        return self.chain[-1]



    def get_block(self, index: int) -> Block:

        if 0 <= index < len(self.chain):

            return self.chain[index]

        raise IndexError("Block index out of range")



    def get_chain(self) -> List[Block]:

        return self.chain



    def validate_chain(self) -> bool:

        for i in range(1, len(self.chain)):

            current = self.chain[i]

            previous = self.chain[i-1]



            if current.hash != current.compute_hash():

                return False



            if current.previous_hash != previous.hash:

                return False



        return True



    def validate_block(self, block: Block) -> bool:

        if block.index > 0:

            previous = self.get_block(block.index - 1)

            if block.previous_hash != previous.hash:

                return False

        if block.hash != block.compute_hash():

            return False

        return True



    def get_transactions_for_vehicle(self, vehicle_hash: str) -> List[Transaction]:

        txs = []

        for block in self.chain:

            for tx in block.transactions:

                if tx.vehicle_hash == vehicle_hash:

                    txs.append(tx)

        # Check pending too

        for tx in self.pending_transactions:

            if tx.vehicle_hash == vehicle_hash:

                txs.append(tx)

        return txs



    def get_chain_length(self) -> int:

        return len(self.chain)



    def get_total_transactions(self) -> int:

        total = 0

        for block in self.chain:

            total += len(block.transactions)

        return total



    def get_statistics(self) -> dict:

        total_txs = self.get_total_transactions()

        blocks = self.get_chain_length()

        return {

            "blocks": blocks,

            "total_transactions": total_txs,

            "avg_txs_per_block": total_txs / max(1, blocks - 1), # Excluding genesis

            "pending_transactions": len(self.pending_transactions)

        }





class PoABlockchain(Blockchain):

    """

    Permissioned blockchain with round-robin Proof-of-Authority.



    Only registered validators (the RSUs) may seal blocks. Each validator owns an

    ECDSA (secp256k1) key; the sealing validator signs the block hash and every

    transaction it includes. Timing statistics use the simulation clock so that

    latency / TPS numbers are consistent with the simulated network.

    """



    def __init__(self, validators: List[str], config=None, block_interval: float = 2.0):

        super().__init__(config)

        from ecdsa import SigningKey, SECP256k1

        self.validators = list(validators)

        self.keys = {v: SigningKey.generate(curve=SECP256k1) for v in self.validators}

        self.block_interval = block_interval

        self._turn = 0

        self.block_signatures: Dict[int, str] = {}

        self.submit_times: Dict[str, float] = {}

        self.tx_index: Dict[str, int] = {}

        self.stats = {"tx_latency_sum": 0.0, "tx_committed": 0, "seal_ms_sum": 0.0,

                      "bytes": 0, "last_block_time": 0.0, "tx_bytes": 0}

        self.latency_samples = deque(maxlen=3000)   # submit -> commit, sim seconds

        self.seal_samples = deque(maxlen=1000)      # validator sealing + signing time, ms

        self.sign_blocks = True



    def public_key(self, validator: str) -> str:

        return self.keys[validator].get_verifying_key().to_string().hex()



    def next_validator(self) -> str:

        return self.validators[self._turn % len(self.validators)]



    def submit(self, tx: Transaction, now: float):

        self.submit_times[tx.tx_id] = now

        self.add_transaction(tx)



    def seal(self, now: float) -> Optional[Block]:

        """Seal pending transactions into a block if the block interval elapsed."""

        if not self.pending_transactions or now - self.stats["last_block_time"] < self.block_interval:

            return None

        validator = self.next_validator()

        t0 = time.perf_counter()

        key = self.keys[validator]

        if self.sign_blocks:

            for tx in self.pending_transactions[: self.config.block_size]:

                if not tx.signature:

                    tx.signature = key.sign(tx.compute_hash().encode()).hex()

        block = self.mine_block(validator, timestamp=now)

        if self.sign_blocks:

            self.block_signatures[block.index] = key.sign(block.hash.encode()).hex()

        self._turn += 1

        seal_ms = (time.perf_counter() - t0) * 1000

        self.stats["seal_ms_sum"] += seal_ms

        self.seal_samples.append(seal_ms)

        self.stats["last_block_time"] = now

        self.stats["bytes"] += len(json.dumps(block.to_dict()))

        for tx in block.transactions:

            self.tx_index[tx.tx_id] = block.index

            submitted = self.submit_times.pop(tx.tx_id, now)

            self.stats["tx_latency_sum"] += now - submitted

            self.latency_samples.append(now - submitted)

            self.stats["tx_bytes"] += len(json.dumps(tx.to_dict()))

            self.stats["tx_committed"] += 1

        return block



    def verify_block_signature(self, block: Block) -> bool:

        from ecdsa import BadSignatureError

        sig = self.block_signatures.get(block.index)

        if block.index == 0 or not self.sign_blocks:

            return True

        if not sig or block.validator not in self.keys:

            return False

        try:

            return self.keys[block.validator].get_verifying_key().verify(bytes.fromhex(sig), block.hash.encode())

        except BadSignatureError:

            return False



    def find_transaction(self, tx_id: str) -> Optional[Dict]:

        idx = self.tx_index.get(tx_id)

        if idx is not None:

            for tx in self.chain[idx].transactions:

                if tx.tx_id == tx_id:

                    return {"block": idx, "confirmed": True, **tx.to_dict()}

        for tx in self.pending_transactions:

            if tx.tx_id == tx_id:

                return {"block": None, "confirmed": False, **tx.to_dict()}

        return None



    def performance(self, sim_time: float) -> Dict:

        blocks = len(self.chain) - 1

        committed = self.stats["tx_committed"]

        return {

            "blocks": len(self.chain),

            "transactions": committed,

            "pending": len(self.pending_transactions),

            "validators": len(self.validators),

            "consensus": "Proof-of-Authority (round-robin RSU validators)",

            "avg_tx_latency_s": self.stats["tx_latency_sum"] / committed if committed else 0.0,

            "tps": committed / sim_time if sim_time > 0 else 0.0,

            "avg_seal_ms": self.stats["seal_ms_sum"] / blocks if blocks else 0.0,

            "block_interval_s": self.block_interval,

            "storage_bytes": self.stats["bytes"],

            "latest_hash": self.chain[-1].hash,

            "next_validator": self.next_validator(),

        }





class CentralizedLedger(PoABlockchain):

    """

    Baseline for experiments: a single central trust server.



    Records are committed immediately (every step) by one authority, without

    distributed validators or signatures. Faster, but a single point of failure

    and trust: whoever controls the server can rewrite history undetected.

    """



    def __init__(self, config=None):

        super().__init__(["CENTRAL"], config, block_interval=0.0)

        self.sign_blocks = False



    def performance(self, sim_time: float) -> Dict:

        perf = super().performance(sim_time)

        perf["consensus"] = "Centralized server (no consensus)"

        return perf



    def validate_chain(self) -> bool:

        """A plain central database has no hash chain to check: modifications go unnoticed."""

        return True
