import time

from typing import List

import sys



from trust.trust_engine import TrustEngine, TrustUpdate

from blockchain.client import BlockchainClient

from config import get_config



class TransactionManager:

    def __init__(self, blockchain_client: BlockchainClient, trust_engine: TrustEngine):

        self.blockchain_client = blockchain_client

        self.trust_engine = trust_engine

        self.config = get_config().blockchain

        self.last_mine_time = time.time()



    def process_detection(self, vehicle_id: str, vehicle_hash: str, ai_result: bool,

                          consensus_result: bool, trust_update: TrustUpdate):



        # Determine if misbehavior was detected

        misbehavior = not ai_result or not consensus_result



        if misbehavior:

            # Decide on misbehavior score based on reasoning

            # Severe if both false, moderate if AI false, minor if consensus false

            if not ai_result and not consensus_result:

                score = 0.9

            elif not ai_result:

                score = 0.6

            else:

                score = 0.3



            self.blockchain_client.report_misbehavior(

                vehicle_hash=vehicle_hash,

                event_type="MISBEHAVIOR_DETECTED",

                score=score

            )



        # Update trust in blockchain

        evidence = {

            "ai_score": trust_update.ai_score,

            "consensus_score": trust_update.consensus_score,

            "reason": trust_update.reason

        }



        self.blockchain_client.update_trust(

            vehicle_hash=vehicle_hash,

            old_trust=trust_update.old_score,

            new_trust=trust_update.new_score,

            evidence=evidence

        )



    def process_batch(self, detections: List[dict]):

        for det in detections:

            # Extract fields

            v_id = det.get("vehicle_id")

            v_hash = det.get("vehicle_hash", v_id) # fallback

            ai_res = det.get("ai_result", True)

            cons_res = det.get("consensus_result", True)

            trust_upd = det.get("trust_update")



            if not trust_upd:

                # Need a valid trust update to process

                continue



            self.process_detection(v_id, v_hash, ai_res, cons_res, trust_upd)



        # Periodic mining is handled by auto_mine usually, but batch can trigger it

        if len(self.blockchain_client.node.blockchain.pending_transactions) >= self.config.block_size:

            self.blockchain_client.node.mine_pending()



    def get_pending_count(self) -> int:

        return len(self.blockchain_client.node.blockchain.pending_transactions)



    def auto_mine(self, interval: float):

        current_time = time.time()

        if current_time - self.last_mine_time >= interval:

            if self.get_pending_count() > 0:

                self.blockchain_client.node.mine_pending()

            self.last_mine_time = current_time
