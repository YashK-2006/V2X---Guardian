from typing import List, Optional

from .chain import Blockchain, Block



class BlockchainNode:

    def __init__(self, node_id: str, blockchain: Blockchain):

        self.node_id = node_id

        self.blockchain = blockchain

        self.peers: List['BlockchainNode'] = []



    def connect_peer(self, peer_node: 'BlockchainNode'):

        if peer_node not in self.peers and peer_node.node_id != self.node_id:

            self.peers.append(peer_node)

            # Add self to peer's peers if not there

            if self not in peer_node.peers:

                peer_node.peers.append(self)



    def broadcast_block(self, block: Block):

        for peer in self.peers:

            peer.receive_block(block)



    def receive_block(self, block: Block) -> bool:

        # Simple validation

        if block.index <= self.blockchain.get_latest_block().index:

            # We already have this block or a longer chain

            return False



        if self.blockchain.validate_block(block):

            self.blockchain.chain.append(block)



            # Remove any pending transactions that are in this block

            block_tx_ids = {tx.tx_id for tx in block.transactions}

            self.blockchain.pending_transactions = [

                tx for tx in self.blockchain.pending_transactions

                if tx.tx_id not in block_tx_ids

            ]



            # Propagate

            for peer in self.peers:

                peer.receive_block(block)

            return True

        else:

            # Might need to sync chain if block is valid but we're missing predecessors

            if block.index > self.blockchain.get_latest_block().index + 1:

                self.sync_chain()

            return False



    def sync_chain(self):

        longest_chain = None

        max_length = self.blockchain.get_chain_length()



        for peer in self.peers:

            peer_chain_len = peer.blockchain.get_chain_length()

            if peer_chain_len > max_length:

                if peer.blockchain.validate_chain():

                    max_length = peer_chain_len

                    longest_chain = peer.blockchain.get_chain()



        if longest_chain:

            self.blockchain.chain = longest_chain.copy()



    def mine_pending(self) -> Optional[Block]:

        if self.blockchain.pending_transactions:

            block = self.blockchain.mine_block(self.node_id)

            if block:

                self.broadcast_block(block)

            return block

        return None
