import sys

import pytest



from blockchain.chain import Blockchain, Block

from blockchain.transaction import Transaction, TransactionType



def test_genesis_block():

    bc = Blockchain()

    assert len(bc.chain) == 1

    assert bc.chain[0].index == 0



def test_add_transaction():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    assert len(bc.pending_transactions) == 1



def test_mine_block():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    block = bc.mine_block("validator1")

    assert block is not None

    assert block.hash == block.compute_hash()

    assert block.merkle_root != ""



def test_chain_validation():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    bc.mine_block("validator1")

    assert bc.validate_chain() is True



def test_block_hash_integrity():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    bc.mine_block("validator1")

    block = bc.get_latest_block()

    block.validator = "hacker"

    assert bc.validate_chain() is False



def test_multiple_blocks():

    bc = Blockchain()

    for i in range(3):

        tx = Transaction(f"tx{i}", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

        bc.add_transaction(tx)

        bc.mine_block("validator1")

    assert bc.get_chain_length() == 4

    assert bc.validate_chain() is True



def test_transactions_for_vehicle():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "MY_HASH", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    bc.mine_block("validator1")

    txs = bc.get_transactions_for_vehicle("MY_HASH")

    assert len(txs) == 1



def test_chain_statistics():

    bc = Blockchain()

    tx = Transaction("tx1", TransactionType.REGISTER_VEHICLE, "hash1", 1000.0, "RSU1", {})

    bc.add_transaction(tx)

    bc.mine_block("validator1")

    stats = bc.get_statistics()

    assert stats["blocks"] == 2

    assert stats["total_transactions"] == 1
