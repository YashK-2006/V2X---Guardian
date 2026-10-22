# API reference



Base URL `http://127.0.0.1:8000`. All responses are JSON. Start the server with

`uvicorn backend.api:app` from the repository root.



## Simulation



| Method | Path | Body / query |

|---|---|---|

| GET | `/api/health`, `/api/simulation/status` | |

| POST | `/api/simulation/start` · `pause` · `resume` · `stop` | |

| POST | `/api/simulation/restart` | `{scenario_id?}` |

| POST | `/api/simulation/speed` | `{factor: 1-10}` |

| GET | `/api/scenarios` | |

| POST | `/api/scenario/load` | `{scenario_id}` |

| GET | `/api/network/geometry`, `/api/network/status` | |



## Vehicles



| Method | Path | Notes |

|---|---|---|

| GET | `/api/vehicles` | live vehicles |

| GET | `/api/vehicles/{id}` | registered vs claimed type, certificate, trust components, consensus, counts |

| GET | `/api/vehicles/{id}/messages/received` | `filter` (all / valid / suspicious / malicious / emergency), `sender`, `type` (CAM / DENM / VAM / MBR), `from`, `to`, `limit`, `privacy` |

| GET | `/api/vehicles/{id}/messages/sent` | `filter`, `type`, `limit`, `privacy` |

| GET | `/api/vehicles/{id}/trust`, `/trust/history` | trust with reasons |

| GET | `/api/vehicles/{id}/attacks` | evidence, before/after report, neighbour reports |

| GET | `/api/vehicles/{id}/blockchain` | the vehicle's transactions |



Received-message fields:



* message: `time`, `sender`, `receiver`, `type`, `content`, `event`

* location: `sender_pos`, `receiver_pos`, `distance`, `latency_ms`

* verdict: `sender_trust`, `ai_confidence`, `probability`, `classification`, `attack_type`, `status`, `reasons`

* security: `sig_status`, `pseudonym`, `tx_id`



## Attacks



| Method | Path | Body |

|---|---|---|

| GET | `/api/attacks/types` | |

| POST | `/api/attacks/launch` | `{attack_type, vehicle_id?, params?}`. `collusion` picks the 2 nearest vehicles too |

| POST | `/api/attacks/stop` | `{vehicle_id?}` (all when omitted) |

| GET | `/api/attacks/active`, `/api/attacks/history`, `/api/attacks/{id}/comparison` | before/after |



## Security, trust and analytics



`/api/alerts`, `/api/evidence` (`privacy`), `/api/evidence/{id}` (`tamper`, `privacy`), `/api/stats`,

`/api/metrics`, `/api/ai/metrics`, `/api/performance`, `/api/timeline`, `/api/graph`, `/api/graph/reset`,

`/api/trust/overview`, `GET|POST /api/trust/weights`, `/api/identity/stats`, `/api/identity/revoked`,

`/api/identity/{id}`.



## Blockchain



`/api/blockchain/status`, `/api/blockchain/blocks?limit&offset`, `/api/blockchain/blocks/{index}` (with hash and

signature checks), `/api/blockchain/transactions?tx_type`, `/api/blockchain/transactions/{tx_id}`,

`/api/blockchain/validate`.



## Replay and experiments



`/api/runs`, `/api/runs/{run_id}/frames?start&end&max_frames`, `/api/runs/{run_id}/alerts`,

`/api/experiments/configs`, `POST /api/experiment/start {config | suite, duration?, repetitions?}`,

`/api/experiments/jobs`, `/api/experiments/results`, `/api/experiments/results/{id}`.



## WebSocket



`/ws/telemetry` carries a `telemetry` frame 10 times per second:



* simulation state: running, paused, speed, sim time, scenario

* `vehicles`, `pedestrians`, `rsus`, `active_attacks`

* `stats`, `metrics`



It also carries these events as they happen:



* `alert`: severity, kind, vehicle, title, message, details

* `block`: index, hash, validator, transaction count and types

* `trust_change`



`/ws/events` carries only the events.
