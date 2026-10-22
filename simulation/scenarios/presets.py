"""

Scenario presets.



Each preset describes traffic density, the vehicle type mix and a schedule of

attacks that the orchestrator launches automatically at the given sim time.

Attack targets are chosen among non-emergency vehicles at launch time.

"""



from dataclasses import dataclass, field

from typing import Dict, List, Optional





@dataclass

class ScheduledAttack:

    at_time: float            # sim seconds after scenario start

    attack_type: str

    count: int = 1            # number of distinct attacker vehicles





@dataclass

class ScenarioPreset:

    id: str

    name: str

    description: str

    period: float = 1.5                        # seconds between departures (lower = denser)

    type_mix: Optional[Dict[str, float]] = None

    attacks: List[ScheduledAttack] = field(default_factory=list)

    seed: int = 42





SCENARIOS: Dict[str, ScenarioPreset] = {p.id: p for p in [

    ScenarioPreset(

        "normal", "Normal Traffic",

        "Mixed urban traffic with no attackers. Baseline for false-positive rate.",

    ),

    ScenarioPreset(

        "high_traffic", "High Traffic",

        "Dense traffic (one departure every 0.6 s) without attackers.",

        period=0.6, seed=7,

    ),

    ScenarioPreset(

        "emergency_vehicle", "Emergency Vehicles",

        "Legitimate ambulances, fire trucks and police broadcasting emergency DENMs.",

        type_mix={"ambulance": 0.10, "firetruck": 0.06, "police": 0.08}, seed=11,

    ),

    ScenarioPreset(

        "emergency_spoofing", "Emergency Vehicle Spoofing",

        "A regular car claims to be an ambulance and broadcasts fake emergency priority.",

        attacks=[ScheduledAttack(20, "emergency_spoofing")], seed=21,

    ),

    ScenarioPreset(

        "multiple_attackers", "Multiple Attackers",

        "Several attackers perform independent falsification attacks.",

        attacks=[

            ScheduledAttack(15, "false_position"),

            ScheduledAttack(20, "false_speed"),

            ScheduledAttack(25, "emergency_spoofing"),

            ScheduledAttack(30, "fake_accident"),

        ], seed=31,

    ),

    ScenarioPreset(

        "sybil", "Sybil Attack",

        "One attacker fabricates several ghost identities around itself.",

        attacks=[ScheduledAttack(20, "sybil")], seed=41,

    ),

    ScenarioPreset(

        "replay", "Replay Attack",

        "An attacker re-broadcasts previously captured messages from other vehicles.",

        attacks=[ScheduledAttack(20, "replay")], seed=51,

    ),

    ScenarioPreset(

        "mixed", "Mixed Attacks",

        "All attack families active across the network.",

        period=1.0,

        attacks=[

            ScheduledAttack(10, "emergency_spoofing"),

            ScheduledAttack(15, "sybil"),

            ScheduledAttack(20, "replay"),

            ScheduledAttack(25, "gps_spoofing"),

            ScheduledAttack(30, "message_flooding"),

            ScheduledAttack(35, "false_heading"),

            ScheduledAttack(40, "fake_accident"),

            ScheduledAttack(45, "message_injection"),

        ], seed=61,

    ),

]}



DEFAULT_SCENARIO = "normal"





def get_scenario(scenario_id: str) -> ScenarioPreset:

    return SCENARIOS.get(scenario_id) or SCENARIOS[DEFAULT_SCENARIO]





def list_scenarios() -> List[Dict]:

    return [

        {"id": s.id, "name": s.name, "description": s.description,

         "attacks": [a.attack_type for a in s.attacks], "density_period": s.period}

        for s in SCENARIOS.values()

    ]
