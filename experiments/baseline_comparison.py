"""

Baseline comparison on the live pipeline (same traffic and attacks for every system):



    No protection        detector off, no trust management

    Rules only           plausibility / crypto rules, trust + blockchain

    AI only              trained model only, trust + blockchain

    Centralized trust    hybrid detector, central trust server instead of the blockchain

    Full system          hybrid detector + trust + reputation + PoA blockchain (proposed)



    python -m experiments.baseline_comparison      (same as: experiment_runner --suite baselines)

"""



from typing import List



from experiments.experiment_runner import ExperimentSpec, main as runner_main



ATTACKS = [

    {"type": "emergency_spoofing", "at": 15},

    {"type": "false_position", "at": 20},

    {"type": "gps_spoofing", "at": 25},

    {"type": "sybil", "at": 30},

    {"type": "replay", "at": 35},

    {"type": "fake_accident", "at": 40},

    {"type": "message_flooding", "at": 45},

    {"type": "collusion", "at": 50},

]





def baseline_specs(duration: float = 150.0, repetitions: int = 2) -> List[ExperimentSpec]:

    base = dict(scenario="normal", duration=duration, repetitions=repetitions, attacks=ATTACKS)

    return [

        ExperimentSpec(name="No protection", detector_mode="none", trust_enabled=False, **base),

        ExperimentSpec(name="Rules only", detector_mode="rules", **base),

        ExperimentSpec(name="AI only", detector_mode="model", **base),

        ExperimentSpec(name="Centralized trust", ledger="centralized", **base),

        ExperimentSpec(name="Full system (proposed)", **base),

    ]





if __name__ == "__main__":

    runner_main(["--suite", "baselines"])
