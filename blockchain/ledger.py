import os

import json

from typing import List

from .chain import Blockchain, Block

from .transaction import Transaction



class Ledger:

    def __init__(self, ledger_dir: str):

        self.ledger_dir = ledger_dir

        os.makedirs(self.ledger_dir, exist_ok=True)

        self.chain_file = os.path.join(self.ledger_dir, "chain.json")



    def save_chain(self, blockchain: Blockchain):

        chain_data = [block.to_dict() for block in blockchain.get_chain()]

        with open(self.chain_file, 'w') as f:

            json.dump(chain_data, f, indent=2)



    def load_chain(self, filepath: str = None) -> Blockchain:

        target_file = filepath or self.chain_file

        blockchain = Blockchain()

        if os.path.exists(target_file):

            try:

                with open(target_file, 'r') as f:

                    chain_data = json.load(f)



                chain = []

                for b_data in chain_data:

                    chain.append(Block.from_dict(b_data))



                if chain:

                    blockchain.chain = chain



            except Exception as e:

                print(f"Error loading chain: {e}")



        return blockchain



    def save_block(self, block: Block):

        # We append to a block log or just rewrite the whole chain

        # For simplicity, load, append and save.

        blockchain = self.load_chain()

        # If it's a new block (not genesis if it exists)

        if not blockchain.chain or block.index > blockchain.get_latest_block().index:

            blockchain.chain.append(block)

            self.save_chain(blockchain)

        elif block.index == blockchain.get_latest_block().index + 1:

            blockchain.chain.append(block)

            self.save_chain(blockchain)



    def query_by_vehicle(self, vehicle_hash: str) -> List[Transaction]:

        blockchain = self.load_chain()

        return blockchain.get_transactions_for_vehicle(vehicle_hash)



    def query_by_time_range(self, start: float, end: float) -> List[Transaction]:

        blockchain = self.load_chain()

        txs = []

        for block in blockchain.chain:

            if start <= block.timestamp <= end:

                for tx in block.transactions:

                    txs.append(tx)

            elif block.timestamp > end:

                break

        return txs



    def query_by_event_type(self, event_type: str) -> List[Transaction]:

        blockchain = self.load_chain()

        txs = []

        for block in blockchain.chain:

            for tx in block.transactions:

                if getattr(tx, 'event_type', None) == event_type:

                    txs.append(tx)

        return txs



    def get_ledger_size(self) -> int:

        if os.path.exists(self.chain_file):

            return os.path.getsize(self.chain_file)

        return 0



    def get_statistics(self) -> dict:

        blockchain = self.load_chain()

        stats = blockchain.get_statistics()

        stats['ledger_size_bytes'] = self.get_ledger_size()

        return stats
