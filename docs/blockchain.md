# Blockchain, smart contract and identity



## Ledger (`blockchain/chain.py`)



* **Permissioned PoA.** The 5 RSUs are the only validators. They seal blocks in round-robin order every 2 s of

  simulated time when transactions are pending.

* **Integrity.** Blocks contain a Merkle root and are SHA-256 hash-chained. The sealing validator signs each

  transaction and the block hash with its ECDSA secp256k1 key.

* **Verification.** `/api/blockchain/validate` recomputes all hashes and checks all block signatures.

* **Statistics.**

  * transaction latency (submit → commit, average and p95)

  * TPS

  * sealing / consensus time

  * storage

  * replication overhead

* `CentralizedLedger` is the experiment baseline. It is a single server that commits immediately, with no

  validators, no signatures and no hash-chain check, so insider modifications go unnoticed.



## Transactions



| Type | Written when |

|---|---|

| `REGISTER_VEHICLE` | a vehicle enters the network (registered type + enrollment) |

| `MISBEHAVIOR_REPORT` | detection probability > 0.9 |

| `EVIDENCE_RECORD` | with a report: evidence id and SHA-256 hash of the full evidence record |

| `TRUST_UPDATE` | detection probability > 0.6 (trust before/after, reason) |

| `BLACKLIST` | trust < 0.15 (certificate revocation) |

| `REHABILITATE` | blacklisted vehicle clean for 45 s (probation trust 0.45) |

| `REPUTATION_UPDATE` | available for consensus snapshots |



Vehicle identifiers on-chain are pseudonymous hashes (`sha256("v2x:"+id)`).



## Smart contract (`TrustManagementContract`)



```

IF p > 0.90   → decrease trust, record report + evidence hash, flag, notify network (RSU warning)

ELIF p > 0.60 → decrease trust (suspicious)

IF trust < 0.15 → blacklist, revoke certificates, notify network

IF blacklisted AND clean for probation period → rehabilitate

```



Only authorised RSUs may call the contract (access control). Evidence verification recomputes the hash of the

stored record and compares it with the on-chain value (`/api/evidence/{id}`, `?tamper=true` demonstrates detection).



## Identity and privacy (`v2x/identity.py`)



* **Enrollment.** A certificate authority enrolls each vehicle with its registered type.

* **Pseudonym certificates.**

  * Issued every 60 s.

  * Each one holds a fresh ECDSA P-256 key and a pseudonym, is bound to the registered type, and is signed by

    the CA.

* **Message signing.** Messages are signed with the current pseudonym key. Receivers verify the CA signature

  on the certificate (cached) and the message signature.

* **Revocation.** Only the CA can link pseudonyms to a vehicle. On blacklisting, all of that vehicle's

  certificates go on the CRL. Rehabilitation issues a fresh pseudonym certificate.

* **Privacy view.**

  * API: `?privacy=true`. Dashboard: the eye toggle.

  * Shows pseudonyms instead of vehicle ids and coarsens locations to a 50 m grid in message and evidence

    views.
