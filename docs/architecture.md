# Architecture



The framework is one live pipeline, driven by `backend/orchestrator.py`. Every simulation step

(0.1 s of simulated time) runs the full chain below; the API and dashboard only read its results.



```

SUMO (TraCI) / mock grid traffic ─┐   pedestrians (VRU devices)

                                  ▼

   vehicle & pedestrian states ──► message factory (CAM 1 Hz, DENM events, VAM)

                                  ▼

   AttackManager (live attacks: falsify / add / replay / forge messages; hidden ground-truth label)

                                  ▼

   IdentityRegistry: ECDSA P-256 signature with the current pseudonym certificate

                                  ▼

   V2XChannel: V2V 300 m · V2I 500 m · V2P 80 m, distance-dependent loss & latency,

               RSU localisation of the physical transmitter

                                  ▼

   MisbehaviorDetector: 13 rule detectors + multi-class XGBoost/RandomForest

               → Normal / Suspicious / Malicious, attack type, probability, explanations

                                  ▼

   per-receiver history + neighbour reports ─► ReportAggregator (trust-weighted consensus)

                                  ▼

   DynamicTrustEngine: penalty = S·(α·AI + β·consensus + γ·history + δ·ledger); rewards; blacklist; probation

                                  ▼

   TrustManagementContract (smart contract): report, evidence hash, trust update, blacklist, rehabilitation

                                  ▼

   PoABlockchain (5 RSU validators, round-robin, ECDSA-signed blocks)    RSU warnings to vehicles (I2V)

                                  ▼

   alerts · WebSocket events · SQLite batch writes · replay recorder

```



## Components



| Module | Responsibility |

|---|---|

| `simulation/road_network.py`, `scenarios/` | 4×4 grid (2 lanes, traffic lights), 9 vehicle types, cached per-scenario routes, 8 scenario presets |

| `simulation/sumo_manager.py` | TraCI lifecycle, subscriptions, vehicle type/route/acceleration, departures/arrivals |

| `simulation/pedestrians.py` | pedestrians walking junction to junction (V2P) |

| `simulation/attacks.py` | 12 attack types incl. multi-vehicle collusion; ground-truth tagging |

| `v2x/factory.py` | dict-based CAM / DENM / VAM construction |

| `v2x/identity.py` | CA, enrollment, rotating pseudonym certificates, ECDSA signing/verification, CRL |

| `v2x/channel.py` | radio model, delivery, latency and PDR statistics, RSU localisation |

| `ai/rule_detectors.py`, `ai/misbehavior_detector.py` | feature extraction, rules, model fusion |

| `ai/train_detector.py` | data generation from the simulator, model training and evaluation |

| `trust/trust_engine.py`, `trust/reputation.py` | dynamic trust, report aggregation |

| `blockchain/chain.py`, `smart_contract.py` | PoA chain, centralized baseline ledger, rule-based smart contract |

| `backend/evidence.py` | evidence records and their on-chain hash |

| `backend/api.py` | REST + WebSocket API, experiment jobs, replay files |

| `experiments/` | headless experiment runner, baselines, ablation |

| `dashboard/` | React SOC dashboard |



## Threading



The simulation runs in a worker thread at 10 ticks per second (×speed steps per tick). All orchestrator

methods take a re-entrant lock, so API requests read consistent state. The broadcaster task pushes a

`telemetry` frame per tick plus `alert`, `block` and `trust_change` events, and writes batched rows to SQLite

once per second.



## Ground truth vs. what detectors see



Messages carry hidden fields (`_tx`, `_tx_pos`, `_attack`) used only for metrics (confusion matrix,

detection latency, acceptance rates). Detectors only see the public message fields, the registry

(certificate checks) and the RSU localisation estimate.



## Attribution



Accountability normally goes to the certificate holder. For forged identities (unknown certificate, Sybil

ghosts) and replays, the RSUs' transmitter localisation is used, and a vehicle is only blamed when the

localisation is unambiguous (nearest vehicle within 10 m and at least 4 m closer than the next one).
