import sys

import pytest



from v2x.message import V2XMessage, MessageType, EventType



class MockMessageBus:

    def __init__(self):

        self.messages = []

    def publish(self, msg):

        self.messages.append(msg)

    def retrieve(self):

        return self.messages

    def get_in_range(self, x, y, radius):

        return [m for m in self.messages if ((m.position_x - x)**2 + (m.position_y - y)**2)**0.5 <= radius]

    def get_stats(self):

        return {"count": len(self.messages)}



def test_cam_message_creation():

    msg = V2XMessage(

        vehicle_id="V1", vehicle_hash="h1", latitude=0.0, longitude=0.0,

        position_x=10.0, position_y=20.0, speed=15.0, acceleration=1.0,

        heading=90.0, lane_id="l1", message_type=MessageType.CAM

    )

    assert msg.message_type == MessageType.CAM

    assert msg.vehicle_id == "V1"



def test_denm_message_creation():

    msg = V2XMessage(

        vehicle_id="V1", vehicle_hash="h1", latitude=0.0, longitude=0.0,

        position_x=10.0, position_y=20.0, speed=15.0, acceleration=1.0,

        heading=90.0, lane_id="l1", message_type=MessageType.DENM,

        metadata={"event_type": EventType.ACCIDENT}

    )

    assert msg.metadata["event_type"] == EventType.ACCIDENT



def test_message_serialization():

    msg = V2XMessage(

        vehicle_id="V1", vehicle_hash="h1", latitude=0.0, longitude=0.0,

        position_x=10.0, position_y=20.0, speed=15.0, acceleration=1.0,

        heading=90.0, lane_id="l1", message_type=MessageType.CAM

    )

    data = msg.to_dict()

    msg2 = V2XMessage.from_dict(data)

    assert msg.message_id == msg2.message_id



def test_message_signature():

    msg = V2XMessage(

        vehicle_id="V1", vehicle_hash="h1", latitude=0.0, longitude=0.0,

        position_x=10.0, position_y=20.0, speed=15.0, acceleration=1.0,

        heading=90.0, lane_id="l1", message_type=MessageType.CAM

    )

    msg.compute_signature("secret")

    assert msg.verify_signature("secret") is True

    assert msg.verify_signature("wrong") is False



def test_message_types():

    assert MessageType.CAM.value == "CAM"

    assert MessageType.DENM.value == "DENM"



def test_message_bus_publish():

    bus = MockMessageBus()

    msg = V2XMessage(vehicle_id="V1", vehicle_hash="h", latitude=0, longitude=0, position_x=0, position_y=0, speed=0, acceleration=0, heading=0, lane_id="", message_type=MessageType.CAM)

    bus.publish(msg)

    assert len(bus.retrieve()) == 1



def test_message_bus_range_filter():

    bus = MockMessageBus()

    msg1 = V2XMessage(vehicle_id="V1", vehicle_hash="h", latitude=0, longitude=0, position_x=0, position_y=0, speed=0, acceleration=0, heading=0, lane_id="", message_type=MessageType.CAM)

    msg2 = V2XMessage(vehicle_id="V2", vehicle_hash="h", latitude=0, longitude=0, position_x=100, position_y=0, speed=0, acceleration=0, heading=0, lane_id="", message_type=MessageType.CAM)

    bus.publish(msg1)

    bus.publish(msg2)

    in_range = bus.get_in_range(0, 0, 50)

    assert len(in_range) == 1



def test_message_bus_statistics():

    bus = MockMessageBus()

    bus.publish(V2XMessage(vehicle_id="V1", vehicle_hash="h", latitude=0, longitude=0, position_x=0, position_y=0, speed=0, acceleration=0, heading=0, lane_id="", message_type=MessageType.CAM))

    assert bus.get_stats()["count"] == 1
