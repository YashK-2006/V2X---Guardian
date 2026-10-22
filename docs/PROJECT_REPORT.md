# V2X AI + Blockchain Trust Framework: Project Report



*SUMO-based V2X simulation with AI misbehaviour detection, dynamic trust and reputation management,

a permissioned blockchain for trust records and evidence, and a real-time security dashboard.*



---



## Contents



1. [Summary](#1-summary)

2. [Starting point: audit of the original project](#2-starting-point-audit-of-the-original-project)

3. [Plan and phases](#3-plan-and-phases)

4. [System architecture](#4-system-architecture)

5. [Feature coverage against the specification](#5-feature-coverage-against-the-specification)

6. [Components in detail](#6-components-in-detail)

7. [Attacks and how each is detected](#7-attacks-and-how-each-is-detected)

8. [AI model results](#8-ai-model-results)

9. [Live detection results](#9-live-detection-results)

10. [Experiments and comparisons](#10-experiments-and-comparisons)

11. [Performance](#11-performance)

12. [The key demonstration: emergency vehicle spoofing](#12-the-key-demonstration-emergency-vehicle-spoofing)

13. [Dashboard](#13-dashboard)

14. [API overview](#14-api-overview)

15. [Testing and verification](#15-testing-and-verification)

16. [How to run](#16-how-to-run)

17. [Design decisions and limitations](#17-design-decisions-and-limitations)

18. [File map](#18-file-map)



---



## 1. Summary



| Item | Result |

|---|---|

| Specification features implemented | **25 / 25** (§5) |

| Attack types simulated and detected | **12**, including multi-vehicle collusion |

| Vehicle types | **9** (car, SUV, taxi, bus, truck, motorcycle, ambulance, fire truck, police) plus pedestrians |

| Detection (live, all attacks at once) | **99.2–99.8 %** of malicious messages detected |

| False-positive rate (live) | **0.006–0.01 %** of honest messages |

| Offline model (XGBoost, 14 classes) | accuracy **99.57 %**, binary F1 **99.23 %**, FPR **0.01 %** |

| Emergency spoofing detection | **0.4–0.7 s** after the attack starts, p ≈ 0.99 |

| Time from attack to blacklisting | **≈ 3–4 s** |

| Malicious messages accepted by receivers | **0.07 %** (full system) vs **87.8 %** (no protection) |

| Insider tampering of trust records | detected on the blockchain; **undetected** with a central server |

| Automated tests | **81 passing** |



Every number shown in the dashboard is computed by the running pipeline against the ground truth of

the attack injector. There is no mock data.



---



## 2. Starting point: audit of the original project



The original repository already contained modules for AI, trust, blockchain and V2X. The audit found

that **none of them were connected to the running system**. The backend orchestrator used only SUMO and

generated everything else.



| Area | Original state | Problem |

|---|---|---|

| Orchestrator | imported only `SumoManager` | AI, trust, blockchain, V2X and attack modules were never called |

| "Malicious" vehicles | chosen by `hash(vehicle_id) % 10` | random per run, no actual attack behaviour |

| Detection rate | `94 + sin(t) + random()` | fabricated number |

| Trust | fixed −0.01 / +0.005 per step | not evidence-based |

| Blockchain counters | random increments | no transactions were recorded |

| AI models | binary, never trained, no model files | features used simulator ground truth (an "oracle") |

| Vehicle types | none (all default) | no emergency vehicles, so spoofing was impossible |

| Message history | not stored | no per-receiver history, no API |

| Dashboard AI / Blockchain / Trust / Experiments pages | hard-coded numbers | controls sent nothing to the backend |

| Dashboard CSS | global `* { padding: 0 }` | overrode every Tailwind spacing utility |

| Code | 30 files with `sys.path.insert('d:/Projects/...')` | Windows-only path |

| Docs | described features that did not exist | e.g. round-robin PoA, WebSocket event types |



---



## 3. Plan and phases



Decisions taken with the user at the start:



| Decision | Choice |

|---|---|

| AI scope | Tree models + rule detectors (multi-class XGBoost / RandomForest); no deep learning or GNN |

| Delivery | Phased, demo-first |



| Phase | Goal | Delivered |

|---|---|---|

| **1** Real pipeline + key demo | Connect everything end to end; emergency-spoofing demo with no mock data | vehicle types; V2X channel; identity; attack injection; detection; trust; smart contract; PoA chain; evidence; message history; alerts; vehicle page (8 tabs); Control Center |

| **2** Attacks, scenarios, analytics | All attacks, scenario presets, communication graph, real analytics pages | 11 attacks; 8 scenarios; communication graph; real AI / Trust / Blockchain pages; blockchain explorer with evidence verification |

| **3** Identity, performance, replay, experiments, cleanup | Remaining spec items and research tooling | collusion; ECDSA pseudonym PKI + CRL; privacy view; V2P pedestrians; RSU warnings; performance page; replay; experiment runner with baselines and ablation; demo script; docs; cleanup |



---



## 4. System architecture



Every simulation step (0.1 s of simulated time) runs the full chain:



```

 SUMO (TraCI) ─ vehicles ─┐        pedestrians (V2P devices)

                          ▼

   Message factory: CAM (1 Hz), DENM (events), VAM (pedestrians)

                          ▼

   Attack injection (12 attack types, hidden ground-truth label)

                          ▼

   ECDSA signature with the current pseudonym certificate

                          ▼

   Radio channel: V2V 300 m · V2I 500 m · V2P 80 m, loss + latency, RSU transmitter localisation

                          ▼

   Misbehaviour detection: 13 rule detectors + XGBoost → Normal / Suspicious / Malicious

                          ▼

   Received-message history (per vehicle) + neighbour reports → reputation consensus

                          ▼

   Dynamic trust:  penalty = S · (α·AI + β·consensus + γ·history + δ·ledger)

                          ▼

   Smart contract: report · evidence hash · trust update · blacklist · rehabilitation

                          ▼

   PoA blockchain (5 RSU validators)   +   RSU warnings to nearby vehicles (I2V)

                          ▼

   Alerts · WebSocket (10 Hz) · SQLite · replay recorder · dashboard

```



| Layer | Technology |

|---|---|

| Traffic | Eclipse SUMO 1.27 via TraCI (a mock grid model is used if SUMO is unavailable) |

| Backend | Python 3.11, FastAPI, WebSockets, SQLAlchemy (SQLite) |

| AI | scikit-learn (RandomForest), XGBoost |

| Crypto | `cryptography` (ECDSA P-256 for vehicles/CA), `ecdsa` (secp256k1 for validators) |

| Frontend | React 19, TypeScript, Vite, Tailwind 4, Zustand, Recharts |



---



## 5. Feature coverage against the specification



| # | Spec feature | Status | Implementation |

|---|---|---|---|

| 1 | SUMO simulation | ✅ | 4×4 grid, 2 lanes, traffic lights, routes, lane changing, dynamic entry/exit, speed control, cached scenarios |

| 1 | Vehicle types | ✅ | 9 SUMO vTypes with realistic mix; per-vehicle ID, type, position, speed, acceleration, heading, lane, route, trust, status |

| 2 | V2X communication | ✅ | V2V, V2I, V2N (reports to ledger), V2P (pedestrians); CAM, DENM (emergency, congestion, accident, hazard, lane change), VAM, RSU warnings |

| 3 | Received message history | ✅ | per receiver: time, sender, receiver, type, content, both locations, distance, latency, sender trust, AI confidence, classification, attack type, tx id; filters: all / valid / suspicious / malicious / emergency / sender / type / time range |

| 4 | AI misbehaviour detection | ✅ | 12 attack types + revoked identity; 13 rules + trained model |

| 5 | Emergency vehicle spoofing | ✅ | fake ambulance / police / fire truck, fake emergency priority DENMs; type-consistency check against registered type |

| 6 | AI model | ✅ | RandomForest + XGBoost, multi-class; Normal / Suspicious / Malicious, probability, attack type, confidence |

| 7 | Trust management | ✅ | dynamic, evidence-based, weighted formula, history with reasons |

| 8 | Reputation management | ✅ | trust-weighted neighbour reports; resistant to lying reporters |

| 9 | Blockchain layer | ✅ | permissioned PoA, immutable hash chain, signed blocks, evidence hashes, audit/explorer |

| 10 | Smart contracts | ✅ | rule engine: report, evidence, trust update, flag, notify, blacklist, rehabilitate, access control |

| 11 | Identity & authentication | ✅ | CA enrollment, certificates with registered type, ECDSA signatures, pseudonyms, revocation (CRL) |

| 12 | Privacy management | ✅ | rotating pseudonyms, CA-only linkability, privacy view (pseudonyms + 50 m location coarsening), on-chain pseudonymous hashes |

| 13 | Evidence management | ✅ | attack id, vehicle, type, time, location, sender, receivers, original message, expected vs observed, AI probability, trust before/after, tx, block |

| 14 | Real-time alerts | ✅ | WebSocket alerts, toasts, alert feed; RSUs notify nearby vehicles |

| 15 | Vehicle detail page | ✅ | 8 tabs: Overview, Messages Sent, Messages Received, Behavior, AI Analysis, Trust History, Attacks, Blockchain |

| 16 | Communication graph | ✅ | force-directed graph, per-link valid / suspicious / malicious counts, forged-identity nodes |

| 17 | Trust history | ✅ | chart over time with reason for each change |

| 18 | Attack simulation controls | ✅ | checkbox list of 12 attacks, vehicle selector, launch / stop |

| 19 | Before / after comparison | ✅ | trust, status, claimed type, detection time and probability, on-chain records, timeline |

| 20 | Dashboard analytics | ✅ | vehicle, communication, security and blockchain statistics |

| 21 | AI performance dashboard | ✅ | accuracy, precision, recall, F1, FPR, confusion matrices (offline + live), per-attack results, feature importance |

| 22 | V2X / blockchain performance | ✅ | latency (p50/p95, end-to-end), PDR, loss, throughput, overhead; tx latency, TPS, consensus time, storage; inference time, detection latency, CPU, memory |

| 23 | Scenario management | ✅ | 8 presets (normal, high traffic, emergency, spoofing, multiple attackers, Sybil, replay, mixed) |

| 24 | Simulation controls | ✅ | start, pause, resume, stop, speed ±, restart; sim time, vehicles, density, scenario, attack status |

| 25 | Recommended architecture | ✅ | as in §4, plus database, replay and experiments |



---



## 6. Components in detail



### 6.1 Traffic and vehicles



| Vehicle type | SUMO class | Share (default mix) | Emergency |

|---|---|---|---|

| Car | passenger | 44 % | |

| SUV | passenger | 14 % | |

| Taxi | taxi | 10 % | |

| Motorcycle | motorcycle | 9 % | |

| Truck | truck | 8 % | |

| Bus | bus | 6 % | |

| Police | authority | 4 % | ✔ |

| Ambulance | emergency | 3 % | ✔ |

| Fire truck | emergency | 2 % | ✔ |



In addition, 12 pedestrians carrying V2X devices walk the road network (V2P).



### 6.2 V2X messages and radio



| Message | Sender | Rate | Content |

|---|---|---|---|

| CAM | every vehicle | 1 Hz | position, speed, acceleration, heading, lane, claimed type, emergency flag |

| DENM | emergency vehicles, stopped vehicles, lane changes | event-driven | event type, location, severity |

| VAM | pedestrians | 1 Hz | pedestrian position and motion |

| MBR (RSU warning) | RSUs | when a sender is flagged or blacklisted | subject vehicle, reason, tx id |



| Link | Range | Measured (live) |

|---|---|---|

| V2V | 300 m | radio latency 2.1 ms avg, 3.2 ms p95 |

| V2I (5 RSUs) | 500 m | packet delivery ratio ≈ 92 % |

| V2P | 80 m | ≈ 29 receivers per broadcast |



Each message carries an ECDSA signature (71 B) and a pseudonym certificate (120 B). That is 191 B of

security overhead, about 49 % of an average 392 B message.



### 6.3 Identity and privacy



| Mechanism | Detail |

|---|---|

| Certificate authority | enrolls each vehicle with its **registered type** |

| Pseudonym certificates | new ECDSA P-256 key and pseudonym every 60 s, signed by the CA |

| Message authentication | every message signed; receivers verify the CA signature and the message signature |

| Linkability | only the CA can link pseudonyms to a vehicle |

| Revocation | blacklisting puts all of a vehicle's certificates on the CRL |

| Privacy view | dashboard / API show pseudonyms instead of IDs, locations rounded to 50 m |

| On-chain identity | `sha256("v2x:" + id)` pseudonymous hash, never the raw ID |



### 6.4 Trust and reputation



Penalty for a detected misbehaviour:



```

penalty = S × (α·p_AI + β·consensus + γ·history + δ·ledger)

          α = 0.35   β = 0.25   γ = 0.25   δ = 0.15    (adjustable in the dashboard)

          S = 0.36 (malicious) / 0.10 (suspicious)

```



| Factor | Meaning |

|---|---|

| p_AI | fused detector probability |

| consensus | trust-weighted share of neighbours that flagged the sender |

| history | previous offences (0 → 1 after 3) |

| ledger | misbehaviour already recorded on the blockchain |



| Trust range | Status |

|---|---|

| ≥ 0.60 | Trusted |

| 0.30 – 0.60 | Suspicious |

| < 0.30 | Malicious |

| < 0.15 | Blacklisted (certificates revoked) |



* **Recovery:** honest messages add +0.004 each, after a 5 s cool-down.

* **Rehabilitation:** a blacklisted vehicle that stays clean for 45 s is reinstated on probation at trust 0.45

  with a new pseudonym certificate.

* **Reputation:** receivers file reports and one vote per reporter is counted, weighted by the reporter's

  trust. Colluders vouching for each other or falsely accusing others have little effect because their own

  trust collapses.



### 6.5 Blockchain and smart contract



| Property | Value |

|---|---|

| Type | Permissioned, Proof-of-Authority |

| Validators | 5 RSUs, round-robin |

| Block interval | 2 s (when transactions are pending) |

| Integrity | Merkle root, SHA-256 hash chain, ECDSA-signed transactions and blocks |

| Access control | only authorised RSUs may call the contract |



| Transaction | Written when |

|---|---|

| `REGISTER_VEHICLE` | vehicle enters the network |

| `MISBEHAVIOR_REPORT` | detection probability > 0.9 |

| `EVIDENCE_RECORD` | with each report: evidence id + SHA-256 hash |

| `TRUST_UPDATE` | detection probability > 0.6 |

| `BLACKLIST` | trust < 0.15 |

| `REHABILITATE` | clean for the probation period |



```

IF p > 0.90   → decrease trust, record report + evidence hash, flag, notify network

ELIF p > 0.60 → decrease trust (suspicious)

IF trust < 0.15 → blacklist, revoke certificates, notify network

IF blacklisted AND clean for 45 s → rehabilitate

```



### 6.6 Evidence record (example)



| Field | Example |

|---|---|

| Attack ID | ATT-1001 |

| Vehicle / attack type | 1 / Emergency vehicle spoofing |

| Time / location | 00:15.5 / (388.6, 395.2) |

| Expected | registered type: bus |

| Observed | claimed type: ambulance (emergency flag set) |

| AI probability | 99.5 % |

| Neighbour consensus | 3 / 3 flagging |

| Trust before → after | 95.2 → 74.0 |

| Evidence hash | stored on-chain (tx `0x2f78…`, block 8) |

| Verification | hash matches ✔ · "simulate tampering" → mismatch ✘ |



---



## 7. Attacks and how each is detected



| Attack | What the attacker does | Main detector(s) |

|---|---|---|

| Emergency vehicle spoofing | claims to be ambulance / police / fire truck, sends emergency DENMs | claimed type ≠ registered type (certificate); emergency authorisation |

| False position | reports a position 80–250 m away | RSU transmitter localisation (sudden, constant offset) |

| GPS spoofing | position drifts away gradually (4 m/s) | RSU localisation error growing over time |

| False speed | reports speed +18–35 m/s | distance travelled vs claimed speeds |

| False acceleration | reports ±9–14 m/s² | claimed vs implied acceleration |

| False heading | heading 110–180° off | heading vs direction of travel (3 consecutive) |

| Fake accident | DENM accidents ahead where nothing happened | independent vehicles pass at speed; event location moves |

| Message flooding | 10× beacon rate | per-station rate limit |

| Replay | re-broadcasts captured messages of others | duplicate nonce / stale timestamp; RSU localisation for attribution |

| Sybil | fabricates 3 ghost identities | unknown certificate; several identities from one transmitter |

| Message injection | tampered DENMs | ECDSA signature fails |

| Collusion (3 vehicles) | report the same fake accident, claim to be stuck at it, vouch for each other, bad-mouth honest neighbours | only *independent* vehicles count as corroboration; contested reporting group; false presence at the reported event |



The detector also flags messages signed with a **revoked certificate** after blacklisting.



---



## 8. AI model results



Training data comes from 5 headless SUMO runs × 240 s (normal, high traffic, emergency vehicles, mixed)

with random attacks. Every transmitted message is one labelled sample: 50,668 samples after balancing

(38,001 train / 12,667 test). There are 35 receiver-observable features.



### 8.1 Model comparison (held-out test set)



| Model | Accuracy | Macro F1 (14 classes) | Precision | Recall | Binary F1 | FPR | Inference / msg | Training |

|---|---|---|---|---|---|---|---|---|

| RandomForest | 99.20 % | 95.13 % | 97.99 % | 98.61 % | 98.30 % | 0.54 % | 2.87 ms | 1.0 s |

| **XGBoost (selected)** | **99.57 %** | **96.27 %** | **99.96 %** | **98.50 %** | **99.23 %** | **0.01 %** | **0.36 ms** | 3.0 s |



### 8.2 Per-class F1 (offline)



| Class | RandomForest | XGBoost |

|---|---|---|

| normal | 0.995 | 0.998 |

| emergency_spoofing | 1.000 | 1.000 |

| collusion | 1.000 | 1.000 |

| fake_accident | 1.000 | 1.000 |

| false_acceleration | 1.000 | 1.000 |

| false_speed | 1.000 | 1.000 |

| message_injection | 1.000 | 1.000 |

| replay | 1.000 | 1.000 |

| sybil | 1.000 | 1.000 |

| message_flooding | 0.999 | 0.999 |

| revoked_identity | 0.999 | 0.999 |

| false_position | 0.931 | 0.904 |

| gps_spoofing | 0.844 | 0.825 |

| false_heading | 0.551 | 0.752 |



A single message cannot tell a constant position offset from gradual GPS drift, and a heading error

cannot be judged before the vehicle moves. The live system resolves these cases with temporal rule labels

(see §9, where typing accuracy is much higher).



### 8.3 Most important features (XGBoost)



| Rank | Feature | Importance |

|---|---|---|

| 1 | duplicate_nonce | 0.212 |

| 2 | revoked | 0.184 |

| 3 | msg_rate | 0.160 |

| 4 | unknown_cert | 0.141 |

| 5 | type_mismatch | 0.123 |

| 6 | claimed_accel | 0.047 |

| 7 | denm_distance | 0.038 |

| 8 | denm_support | 0.016 |

| 9 | bad_signature | 0.012 |

| 10 | accel_mismatch | 0.010 |



### 8.4 Fusion of rules and model



| Situation | Outcome |

|---|---|

| Rule and model agree | probability raised: `1 − (1 − p_rule)(1 − p_model)` |

| Model very sure it is normal (< 5 %) and weak rule (< 0.8) | rule vetoed (removes plausibility false positives) |

| Related attack labels (position / GPS / collusion / fake accident) | temporal rule label wins |

| No trained model available | rules only |



---



## 9. Live detection results



The simulator runs for 150 s with **all attack types active at the same time**, measured per

message against ground truth.



| Scenario | Detection rate | Precision | False-positive rate | Innocent vehicles blacklisted |

|---|---|---|---|---|

| High traffic | **99.82 %** | 99.95 % | **0.006 %** | 0 |

| Mixed attacks | **99.16 %** | 99.98 % | **0.010 %** | 0 |



Per attack (high-traffic run):



| Attack | Malicious msgs | Detected | Correct attack type |

|---|---|---|---|

| Emergency spoofing | 78 | 100 % | 100 % |

| False position | 130 | 100 % | 100 % |

| GPS spoofing | 130 | 96.9 % | 96.9 % |

| False speed | 130 | 100 % | 100 % |

| False acceleration | 129 | 100 % | 100 % |

| False heading | 64 | 100 % | 67 % |

| Fake accident | 54 | 100 % | 100 % |

| Message flooding | 464 | 100 % | 100 % |

| Replay | 122 | 100 % | 100 % |

| Sybil | 102 | 100 % | 100 % |

| Message injection | 43 | 100 % | 100 % |

| Collusion | 462 | 100 % | 97.8 % |

| Revoked identity | 258 | 100 % | 100 % |



### Improvements made during development



| Problem found | Fix | Effect |

|---|---|---|

| Replay/Sybil attribution blamed a queued neighbour | only attribute when RSU localisation is unambiguous | innocent blacklisting: 2 → 0 |

| Fake accidents only 46 % detected | event drift + independent corroboration | 100 % detected |

| Congestion reports at red lights flagged | reporter-on-scene logic | congestion false positives removed |

| Hard braking flagged as false speed | compare with the mean of previous and current speed + model veto | FPR 0.19 % → 0.01 % |

| GPS spoofing labelled as false position | drift rate measured over ≥ 4 s | typing 26 % → 97 % |

| Collusion members labelled as position attacks | "false presence at own reported event" | typing 1 % → 98 % |

| Pedestrians teleporting at junctions | continuous junction-to-junction walking | pedestrian false positives removed |



---



## 10. Experiments and comparisons



The experiment runner executes the complete live pipeline headless. It can be started from the dashboard

or the command line.



### 10.1 Baseline comparison (same traffic and 8 attacks for every system)



| System | Detection rate | FPR | Malicious msgs accepted | Honest msgs rejected | Time to detect | Time to blacklist | Attackers isolated | Ledger latency | Tamper detected |

|---|---|---|---|---|---|---|---|---|---|

| No protection | 0 % | 0 % | **87.8 %** | 0 % | — | never | 0 % | 1.15 s | yes |

| Rules only | 98.9 % | 0.31 % | 0.56 % | 0.45 % | 1.59 s | 5.89 s | 100 % | 1.03 s | yes |

| AI only | 99.6 % | 0.03 % | 0.14 % | 0.27 % | 0.71 s | 4.01 s | 100 % | 1.04 s | yes |

| Centralized trust server | 99.7 % | 0.00 % | 0.07 % | 0.21 % | 0.84 s | 3.94 s | 100 % | **0.00 s** | **no** |

| **Full system (proposed)** | **99.7 %** | **0.00 %** | **0.07 %** | **0.21 %** | **0.84 s** | **3.94 s** | **100 %** | 0.91 s | **yes** |



In the "No protection" row, 12 % of malicious messages are still rejected because their certificates are

unknown or their signatures fail.



**Takeaways**



* Detection and trust management cut the malicious messages that receivers act on from **87.8 % to 0.07 %**.

* Combining rules and AI beats either alone: fewer false positives than rules only, and attackers are

  isolated **33 % faster** (5.89 s → 3.94 s).

* A central server matches the detection results and has zero ledger latency. However, an insider can

  rewrite trust records **without detection**. The blockchain detects this at a cost of about 1 s of

  record latency.



### 10.2 Blockchain vs centralized trust



| Property | PoA blockchain (5 RSUs) | Central server |

|---|---|---|

| Record latency | 1.04 s | 0 s |

| Throughput | 2.0 TPS (load-bound) | 2.0 TPS |

| Storage (150 s run) | 69.7 KB | 67.0 KB |

| Validators / signatures | 5 / ECDSA-signed blocks and transactions | none |

| Single point of failure | no | yes |

| Insider tampering detected | **yes** | **no** |



### 10.3 Other experiment configurations provided



| Config | Question answered |

|---|---|

| exp1_normal | false positives and overhead without attackers |

| exp2_position | false position vs GPS drift |

| exp3_false_event | fake accidents and a colluding group |

| exp4_frequency | flooding and replay in dense traffic |

| exp5_multiple | all attack families together |

| exp6_recovery | blacklisting and rehabilitation after attacks stop |

| exp7_blockchain_vs_centralized | ledger latency vs tamper evidence |

| exp8_emergency_spoofing | spoofers among real emergency vehicles |

| exp9_sybil | forged identities |

| suite: ablation | effect of each trust factor (AI only → + consensus → + history → + ledger) |



---



## 11. Performance



Measured on the live system (SUMO, about 60 vehicles, 12 pedestrians, Apple M4, CPU only).



### 11.1 V2X



| Metric | Value |

|---|---|

| Radio latency (avg / p50 / p95) | 2.13 / 2.13 / 3.18 ms |

| End-to-end latency incl. detection (avg / p95) | 2.41 / 3.45 ms |

| Packet delivery ratio | 91.6 % |

| Receivers per broadcast | 29.4 |

| Average message size | 392 B |

| Security overhead (signature + certificate) | 191 B (48.7 %) |



### 11.2 Blockchain



| Metric | Value |

|---|---|

| Transaction latency (avg / p50 / p95) | 1.09 / 0.90 / 1.90 s |

| Consensus / sealing time (avg / p95) | 1.8 / 2.5 ms |

| Average transaction size | 475 B |

| Storage (≈ 1,600 tx) | 1.1 MB |

| Replication overhead (5 validators) | 3.8 MB |



### 11.3 AI and system



| Metric | Value |

|---|---|

| Inference per message (avg / p95) | 0.32 / 0.54 ms |

| Detection latency, emergency spoofing | 0.4 s (max 0.7 s) |

| Attack → blacklist | 2.9 s |

| Pipeline step (avg / p95) | 9.2 / 11.9 ms |

| Real-time capacity | ≈ 11× faster than real time |

| CPU (avg) | 32 % |

| Memory | ≈ 700 MB (long run incl. 3,000-message history per vehicle) |

| GPU | not needed |



---



## 12. The key demonstration: emergency vehicle spoofing



This is the end-to-end flow requested in the specification, produced by `python run_demo.py`:



| Step | What happens | Evidence in the system |

|---|---|---|

| 1 | Vehicle 1 (registered **bus**) starts claiming to be an **ambulance** | attack launched (Control Center / API) |

| 2 | It broadcasts CAMs with emergency flag + `EMERGENCY_VEHICLE_APPROACH` DENMs | messages in its *Messages Sent* tab |

| 3 | Neighbours and RSUs receive them | *Messages Received* of neighbours (distance, latency) |

| 4 | Detector: registered type ≠ claimed type | rule `type_consistency`, p = 99.5 %, detected after 0.5 s |

| 5 | Trust drops | 95.2 → 74.0 → 44.1 → 11.1 (reasons with neighbour agreement 3/3) |

| 6 | Smart contract records report + evidence hash | `MISBEHAVIOR_REPORT`, `EVIDENCE_RECORD` in block 8 |

| 7 | Trust < 0.15 → blacklist, certificates revoked | `BLACKLIST` transaction, CRL entry |

| 8 | 🚨 alert and toast; RSU warns nearby vehicles | "EMERGENCY VEHICLE SPOOFING — actual bus, claims ambulance" |

| 9 | Clicking a nearby vehicle shows the flagged messages | status 🚨, sender trust 0.0, AI confidence 99.8 %, tx id |



| | Trust | Status | Claimed type | On-chain reports |

|---|---|---|---|---|

| Before | 95.2 | trusted | bus | 0 |

| After | 0.0 | blacklisted | ambulance | 6 |



---



## 13. Dashboard



| Page | Contents |

|---|---|

| Overview | live map (vehicle-type icons, status colours, RSUs, pedestrians), live alerts, vehicle/RSU side panels, communication, security, blockchain and network statistics |

| Control Center | start / pause / stop / speed / restart, scenario selector, attack launcher (12 attacks, vehicle choice), active attacks, before/after panel |

| Vehicle page | 8 tabs: Overview, Messages Sent, Messages Received (filters), Behavior, AI Analysis, Trust History, Attacks (evidence + verify / tamper test), Blockchain |

| Communication | force-directed graph, link statistics, most-flagged senders, forged identities |

| AI Detection | offline and live metrics, confusion matrices, per-attack detection, per-class F1, feature importance, model comparison |

| Trust | distribution, trust over time, recent decisions, trust ranking, adjustable weights |

| Blockchain | explorer (evidence / transaction / block search), chain validation, blocks, transactions, evidence records |

| Performance | V2X, blockchain, AI and system metrics with time-series charts |

| Replay | recorded runs, play / pause / scrub / speed, network state and alerts at any moment |

| Experiments | run configs and suites, job logs, results table and comparison charts |

| (Sidebar) | privacy toggle: pseudonyms and coarsened locations |



---



## 14. API overview



| Group | Examples |

|---|---|

| Simulation | `POST /api/simulation/{start,pause,resume,stop,restart}`, `POST /api/simulation/speed`, `POST /api/scenario/load` |

| Vehicles | `GET /api/vehicles/{id}`, `/messages/received?filter&sender&type&from&to&privacy`, `/messages/sent`, `/trust/history`, `/attacks`, `/blockchain` |

| Attacks | `GET /api/attacks/types`, `POST /api/attacks/launch`, `POST /api/attacks/stop`, `GET /api/attacks/{id}/comparison` |

| Security | `GET /api/alerts`, `/api/evidence`, `/api/evidence/{id}?tamper`, `/api/identity/stats`, `/api/identity/revoked` |

| Analytics | `/api/stats`, `/api/ai/metrics`, `/api/performance`, `/api/trust/overview`, `/api/graph`, `/api/timeline` |

| Blockchain | `/api/blockchain/{status,blocks,transactions,validate}` |

| Replay / experiments | `/api/runs`, `/api/runs/{id}/frames`, `POST /api/experiment/start`, `/api/experiments/results` |

| WebSocket | `/ws/telemetry`: `telemetry` (10 Hz), `alert`, `block`, `trust_change` |



The full reference is in [api_reference.md](api_reference.md).



---



## 15. Testing and verification



| Check | Result |

|---|---|

| Unit + integration tests (`python -m pytest`) | **81 passed**: 66 original + 15 new (identity, channel, rules, detector, replay attack, trust, reputation, contract rules, evidence verification, PoA round-robin, centralized-ledger tamper test, orchestrator end-to-end with all attacks, collusion / V2P / RSU warnings / privacy) |

| Dashboard | `tsc` type-check, `oxlint`, and production build clean |

| API | every endpoint exercised against a running server; no server errors |

| Browser | all pages rendered in headless Chrome with live data |

| End-to-end demo | `run_demo.py` against real SUMO |

| Experiments | baseline suite and blockchain-vs-centralized run via API and CLI |



---



## 16. How to run



```bash

pip install -r requirements.txt           # SUMO must be installed (pip package 'eclipse-sumo' works)

python run_demo.py                        # terminal demo (trains the detector first if needed)



uvicorn backend.api:app --port 8000       # backend (from the repository root)

cd dashboard && npm install && npm run dev   # dashboard → http://localhost:5173



python -m ai.train_detector               # retrain the detector (~4 min)

python -m experiments.baseline_comparison # baseline comparison

python -m experiments.experiment_runner --config exp7_blockchain_vs_centralized

python -m pytest                          # tests (use the mock traffic model, no SUMO needed)

```



| Environment variable | Effect |

|---|---|

| `SUMO_BINARY=sumo-gui` | open the SUMO GUI alongside the dashboard |

| `V2X_MOCK_TRAFFIC=1` | force the built-in traffic model |

| `V2X_PERSIST_RUNS=0` | do not write replay files |



---



## 17. Design decisions and limitations



| Topic | Decision / limitation |

|---|---|

| AI scope | Tree models + rules were chosen over deep learning / GNN. They are fast (< 1 ms), explainable and accurate on this data. A GNN could be added later. |

| Ground truth | Only used for metrics. Detectors see public message fields, certificates and RSU localisation. |

| RSU localisation | Simulated RSSI/AoA estimate (σ = 2.5 m). Real accuracy would be lower. |

| Pedestrians | A simple built-in walking model, not SUMO's pedestrian simulation. |

| Station ID | Messages keep a stable station ID so receivers can track senders across pseudonym changes. The privacy view hides it from users. |

| Blockchain | In-process PoA with 5 simulated validators, not a networked Hyperledger/Ethereum deployment. Latency figures are in simulated time. |

| Traffic network | 4×4 synthetic grid (600 m × 600 m). Real maps can be imported with SUMO's `netconvert`. |

| Model generalisation | Trained on the same simulator. False heading and position-family typing are weaker from single messages (see §8.2). |



---



## 18. File map



| Path | Content |

|---|---|

| `backend/orchestrator.py` | the pipeline (per-step logic, queries, performance, replay) |

| `backend/api.py` | REST + WebSocket API, experiment jobs |

| `backend/evidence.py` | evidence records and hashes |

| `simulation/road_network.py`, `scenarios/` | network, vehicle types, scenario presets |

| `simulation/sumo_manager.py`, `pedestrians.py`, `attacks.py` | SUMO, pedestrians, attack injection |

| `v2x/factory.py`, `identity.py`, `channel.py` | messages, PKI, radio |

| `ai/rule_detectors.py`, `misbehavior_detector.py`, `train_detector.py`, `models/` | detection and training |

| `trust/trust_engine.py`, `reputation.py` | trust and reputation |

| `blockchain/chain.py`, `smart_contract.py`, `transaction.py` | ledger and contract |

| `experiments/` | runner, configs, baselines, ablation, results |

| `dashboard/src/` | React dashboard (pages, components, store, WebSocket hook) |

| `tests/` | 81 tests |

| `docs/` | architecture, detection, blockchain & identity, experiments, API, this report |

| `run_demo.py` | terminal demonstration |
