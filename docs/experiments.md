# Experiments



Experiments run the complete live pipeline headless: SUMO, V2X, attacks, detection, trust, contract and

ledger. They measure against the attack injector's ground truth.



```bash

python -m experiments.experiment_runner --config exp5_multiple      # one config

python -m experiments.experiment_runner --all                       # every config

python -m experiments.baseline_comparison                           # baseline suite

python -m experiments.ablation_study                                # trust-weight ablation

python -m experiments.experiment_runner --config exp1_normal --duration 60 --repetitions 1

```



The same runs can be started from the dashboard's **Experiments** page. Each runs in its own process with its

own SUMO instance. Results are written to `experiments/results/<timestamp>_<name>/` as `results.json` and

`summary.csv`.



## Configs (`experiments/configs/*.yaml`)



| Config | Question |

|---|---|

| exp1_normal | false positives / overhead without attackers |

| exp2_position | false position vs GPS drift |

| exp3_false_event | fake accidents and a colluding group |

| exp4_frequency | flooding and replay under dense traffic |

| exp5_multiple | all attack families together |

| exp6_recovery | isolation and probation-based rehabilitation after attacks stop |

| exp7_blockchain_vs_centralized | ledger latency vs tamper evidence |

| exp8_emergency_spoofing | spoofers among legitimate emergency vehicles |

| exp9_sybil | forged identities |



Config fields are `scenario`, `duration` (sim s), `repetitions`, `attacks` (`type`, `count`, `at`, optional

`duration`), `trust_weights`, `detector_mode`, `trust_enabled`, `ledger` and `variants` (a list of overrides).



## Suites



* **Baselines:** no protection, rules only, AI only, centralized trust, full system. All use the same traffic

  and attacks.

* **Ablation:** trust weights for AI only, AI + consensus, AI + consensus + history, and the full formula.



## Metrics



* **Detection:** detection rate, precision, F1, false-positive rate, accuracy.

* **Impact on receivers:**

  * malicious messages accepted (valid signature, not flagged, sender trusted)

  * honest messages rejected

* **Timing:** detection latency and isolation time.

* **Isolation outcome:** fraction of attackers isolated, number of innocents blacklisted.

* **Trust:** mean trust of honest vs attacking vehicles.

* **Ledger:** transaction latency, TPS, storage, and an insider **tamper test**. The test modifies a committed

  record and checks whether the ledger notices.

* **V2X and AI:** PDR, latency, inference time.
