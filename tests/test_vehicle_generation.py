import sys

import pytest



from simulation.vehicle_manager import VehicleManager, VehicleState



@pytest.fixture

def manager():

    return VehicleManager()



def test_vehicle_state_creation():

    state = VehicleState(

        vehicle_id="V1", position=(10.0, 20.0), latitude=10.0, longitude=20.0,

        speed=15.0, acceleration=1.0, heading=90.0, lane_id="lane_1",

        road_id="road_1", vehicle_type="car", timestamp=1000.0, is_active=True

    )

    assert state.vehicle_id == "V1"

    assert state.position == (10.0, 20.0)



def test_vehicle_identity_hash(manager):

    h1 = manager.generate_identity_hash("V1")

    assert len(h1) == 64



def test_vehicle_manager_register(manager):

    record = manager.register_vehicle("V1")

    assert manager.get_vehicle("V1") == record

    assert "V1" in manager.get_all_vehicles()



def test_vehicle_manager_behavior_assignment(manager):

    manager.assign_behavior_types([f"V{i}" for i in range(10)], 0.1)

    misbehaving = manager.get_vehicles_by_type("misbehaving")

    assert len(misbehaving) == 1



def test_vehicle_manager_range_query(manager):

    manager.register_vehicle("V1")

    manager.register_vehicle("V2")

    manager.update_vehicle_state("V1", VehicleState("V1", (0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, "", "", "", 0.0))

    manager.update_vehicle_state("V2", VehicleState("V2", (100.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, "", "", "", 0.0))

    in_range = manager.get_vehicles_in_range((0.0, 0.0), 150.0)

    assert len(in_range) == 2



def test_vehicle_state_history(manager):

    for i in range(100):

        manager.update_vehicle_state("V1", VehicleState("V1", (i, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, "", "", "", 0.0))

    record = manager.get_vehicle("V1")

    assert len(record.behavior_history) == manager.history_size
