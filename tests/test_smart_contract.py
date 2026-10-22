import sys

import pytest



from blockchain.chain import Blockchain

from blockchain.smart_contract import SmartContract



@pytest.fixture

def contract():

    bc = Blockchain()

    return SmartContract(bc, ["RSU1", "RSU2"])



def test_register_vehicle(contract):

    tx = contract.register_vehicle("HASH1", 0.5, "RSU1")

    assert tx.tx_type.value == "REGISTER_VEHICLE"

    assert contract.get_vehicle_trust("HASH1") == 0.5



def test_record_misbehavior(contract):

    tx = contract.record_misbehavior("HASH1", "SPEEDING", 0.8, "RSU1")

    assert tx.event_type == "SPEEDING"



def test_update_trust(contract):

    contract.register_vehicle("HASH1", 0.5, "RSU1")

    contract.update_trust("HASH1", 0.2, 0.5, {}, "RSU1")

    assert contract.get_vehicle_trust("HASH1") == 0.2



def test_unauthorized_rsu(contract):

    with pytest.raises(PermissionError):

        contract.register_vehicle("HASH1", 0.5, "HACKER_RSU")



def test_reputation_history(contract):

    contract.register_vehicle("HASH1", 0.5, "RSU1")

    contract.update_trust("HASH1", 0.4, 0.5, {}, "RSU1")

    contract.update_trust("HASH1", 0.3, 0.4, {}, "RSU1")

    history = contract.get_reputation_history("HASH1")

    assert len(history) == 3



def test_recover_trust(contract):

    contract.update_trust("HASH1", 0.2, 0.5, {}, "RSU1")

    contract.recover_trust("HASH1", 0.3, {}, "RSU1")

    assert contract.get_vehicle_trust("HASH1") == 0.3
