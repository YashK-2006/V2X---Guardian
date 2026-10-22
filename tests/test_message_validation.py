import sys

import pytest

import time



from v2x.message import V2XMessage, MessageType

from v2x.message_validator import MessageValidator



@pytest.fixture

def validator():

    return MessageValidator()



def get_base_msg(speed=10.0, acc=1.0, head=90.0, ts_offset=0.0, x=0.0):

    return V2XMessage(

        vehicle_id="V1", vehicle_hash="h", latitude=0, longitude=0,

        position_x=x, position_y=0.0, speed=speed, acceleration=acc,

        heading=head, lane_id="l1", message_type=MessageType.CAM,

        timestamp=time.time() + ts_offset

    )



def test_valid_message_passes(validator):

    msg = get_base_msg()

    res = validator.validate(msg)

    assert res.is_valid is True



def test_speed_bounds_violation(validator):

    msg = get_base_msg(speed=200.0)

    res = validator.validate(msg)

    assert res.is_valid is False

    assert res.checks_passed["speed_bounds"] is False



def test_acceleration_bounds_violation(validator):

    msg = get_base_msg(acc=50.0)

    res = validator.validate(msg)

    assert res.is_valid is False

    assert res.checks_passed["acceleration_bounds"] is False



def test_heading_range_violation(validator):

    msg = get_base_msg(head=400.0)

    res = validator.validate(msg)

    assert res.is_valid is False

    assert res.checks_passed["heading_range"] is False



def test_timestamp_freshness(validator):

    msg = get_base_msg(ts_offset=-20.0)

    res = validator.validate(msg)

    assert res.is_valid is False

    assert res.checks_passed["freshness"] is False



def test_position_plausibility(validator):

    msg = get_base_msg(x=100000.0)

    res = validator.validate(msg)

    assert res.is_valid is False

    assert res.checks_passed["position_plausibility"] is False
