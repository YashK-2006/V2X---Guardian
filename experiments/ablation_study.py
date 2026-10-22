"""

Trust-model ablation on the live pipeline: which evidence sources matter?



The trust penalty is S·(α·AI + β·consensus + γ·history + δ·ledger). Each

configuration keeps detection identical and changes only the weights, so the

differences show up in isolation time, attacker trust and honest-vehicle trust.



    python -m experiments.ablation_study      (same as: experiment_runner --suite ablation)

"""



from typing import List



from experiments.baseline_comparison import ATTACKS

from experiments.experiment_runner import ExperimentSpec, main as runner_main



CONFIGS = [

    ("AI only", {"alpha": 1.0, "beta": 0.0, "gamma": 0.0, "delta": 0.0}),

    ("AI + consensus", {"alpha": 0.6, "beta": 0.4, "gamma": 0.0, "delta": 0.0}),

    ("AI + consensus + history", {"alpha": 0.4, "beta": 0.3, "gamma": 0.3, "delta": 0.0}),

    ("Full (AI + consensus + history + ledger)", {"alpha": 0.35, "beta": 0.25, "gamma": 0.25, "delta": 0.15}),

]





def ablation_specs(duration: float = 150.0, repetitions: int = 2) -> List[ExperimentSpec]:

    return [ExperimentSpec(name=name, scenario="normal", duration=duration, repetitions=repetitions,

                           attacks=ATTACKS, trust_weights=weights) for name, weights in CONFIGS]





if __name__ == "__main__":

    runner_main(["--suite", "ablation"])
