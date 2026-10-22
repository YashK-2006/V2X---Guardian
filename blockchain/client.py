from typing import List, Optional, Dict, Any

from .node import BlockchainNode

from .smart_contract import SmartContract



class BlockchainClient:

    def __init__(self, node: BlockchainNode, smart_contract: SmartContract):

        self.node = node

        self.smart_contract = smart_contract



    def register_vehicle(self, vehicle_hash: str, initial_trust: float) -> str:

        tx = self.smart_contract.register_vehicle(vehicle_hash, initial_trust, self.node.node_id)

        self.mine_if_needed()

        return tx.tx_id



    def report_misbehavior(self, vehicle_hash: str, event_type: str, score: float) -> str:

        tx = self.smart_contract.record_misbehavior(vehicle_hash, event_type, score, self.node.node_id)

        self.mine_if_needed()

        return tx.tx_id



    def update_trust(self, vehicle_hash: str, old_trust: float, new_trust: float, evidence: dict) -> str:

        tx = self.smart_contract.update_trust(vehicle_hash, new_trust, old_trust, evidence, self.node.node_id)

        self.mine_if_needed()

        return tx.tx_id



    def get_vehicle_reputation(self, vehicle_hash: str) -> dict:

        trust = self.smart_contract.get_vehicle_trust(vehicle_hash)

        history = self.smart_contract.get_reputation_history(vehicle_hash)

        return {

            "vehicle_hash": vehicle_hash,

            "current_trust": trust,

            "history": history

        }



    def get_recent_transactions(self, count: int) -> List[dict]:

        txs = []

        for block in reversed(self.node.blockchain.chain):

            for tx in reversed(block.transactions):

                txs.append(tx.to_dict())

                if len(txs) >= count:

                    return txs

        # also include pending if needed, but standard is from blocks

        return txs



    def get_blockchain_status(self) -> dict:

        stats = self.node.blockchain.get_statistics()

        stats["validators"] = len(self.smart_contract.authorized_rsus)

        stats["node_id"] = self.node.node_id

        stats["peers"] = len(self.node.peers)

        return stats



    def mine_if_needed(self) -> Optional[dict]:

        # Simple policy: mine if pending reaches block size or immediately (simplified here)

        if len(self.node.blockchain.pending_transactions) > 0:

            block = self.node.mine_pending()

            if block:

                return block.to_dict()

        return None
