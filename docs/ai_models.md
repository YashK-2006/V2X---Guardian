# Misbehaviour detection



Detection combines deterministic rule detectors with a trained multi-class model

(`ai/misbehavior_detector.py`). Every transmitted message gets a verdict:



| Output | Meaning |

|---|---|

| `classification` | Normal (< 0.5), Suspicious (0.5–0.8), Malicious (≥ 0.8) |

| `attack_type` | one of 13 classes (below) or `normal` |

| `probability` | fused misbehaviour probability |

| `confidence` | confidence of the chosen label |

| `rule_hits` | explanations: rule, attack type, score, expected value, observed value |



## Features (receiver-observable only, 35)



Authentication (bad signature, unknown / revoked certificate), identity consistency (claimed vs registered type,

emergency flag), kinematic plausibility against the sender's own history (position jump, implied vs claimed

speed and acceleration, heading vs direction of travel), RSU localisation error and its growth, message rate and

interval, duplicate nonce, message age, DENM corroboration by *independent* nearby vehicles, event drift between

repeated reports, number of stations reporting the same event, membership of a contested reporting group, and

co-located identities.



## Rule detectors (`ai/rule_detectors.py`)



signature check · certificate check · revocation check · type consistency (emergency spoofing) · emergency

authorisation · nonce / timestamp freshness (replay) · RSU localisation (false position vs GPS drift vs

collusion) · speed, acceleration and heading plausibility · rate limit (flooding) · Sybil co-location ·

event corroboration, event stationarity and collusion detection (DENMs).



## Model



`python -m ai.train_detector` runs the simulator headless (5 runs × 240 s over the normal, high-traffic,

emergency and mixed scenarios), launching and stopping random attacks on random vehicles. Every transmitted

message becomes one labelled sample. RandomForest and XGBoost are trained on a stratified 75/25 split; the one

with the best macro-F1 is saved to `ai/models/mbd_model.joblib`, with all metrics in `ai/models/metrics.json`

(accuracy, binary precision / recall / F1 / FPR, per-class report, confusion matrix, inference time).



Classes: normal, emergency_spoofing, false_position, gps_spoofing, false_speed, false_acceleration,

false_heading, fake_accident, message_flooding, replay, sybil, message_injection, collusion, revoked_identity.



## Fusion



* The strongest rule and the model's probability are compared. Agreement raises the probability,

  `1 − (1 − p_rule)(1 − p_model)`.

* A very confident "normal" model verdict (< 5% misbehaviour) vetoes weak rule hits (score < 0.8). Identity and

  cryptographic rules are authoritative.

* Where the model cannot separate related attacks from a single message (false position, GPS spoofing,

  collusion, fake accident), the temporal rule label wins.

* Without a trained model the detector runs on rules only.



Detector modes (`hybrid`, `rules`, `model`, `none`) are used by the experiment baselines.



## Live metrics



Because the attack injector knows the ground truth, the dashboard reports live per-message confusion

matrices, detection rate, precision, false-positive rate, per-attack detection and typing accuracy, detection

latency (launch → first flag) and isolation time (launch → blacklist).
