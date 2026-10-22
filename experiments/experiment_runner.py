"""

Experiment engine running the *live* pipeline headless.



Each experiment runs the full orchestrator (SUMO or mock traffic, V2X channel,

attack injection, detection, trust, smart contract, ledger) for a fixed amount

of simulated time and reports metrics computed against the attack injector's

ground truth.



    python -m experiments.experiment_runner --config exp5_multiple

    python -m experiments.experiment_runner --all

    python -m experiments.experiment_runner --suite baselines     # see experiments/baseline_comparison.py

    python -m experiments.experiment_runner --suite ablation      # see experiments/ablation_study.py

"""



import argparse

import csv

import json

import logging

import os

import random

import statistics

import time

from dataclasses import asdict, dataclass, field

from typing import Any, Dict, List, Optional



import yaml



from config import get_config



logger = logging.getLogger("experiments")



METRIC_KEYS = [

    "detection_rate", "precision", "f1", "false_positive_rate", "accuracy",

    "malicious_acceptance_rate", "honest_rejection_rate",

    "detection_latency_s", "isolation_time_s", "attackers_isolated", "innocents_blacklisted",

    "avg_trust_honest", "avg_trust_attackers",

    "bc_tx_latency_s", "bc_tps", "bc_storage_bytes", "tamper_detected",

    "v2x_pdr", "v2x_latency_ms", "inference_ms", "wall_time_s",

]





@dataclass

class ExperimentSpec:

    name: str = "experiment"

    description: str = ""

    scenario: str = "normal"

    duration: float = 150.0                 # simulated seconds

    repetitions: int = 1

    attacks: List[Dict[str, Any]] = field(default_factory=list)  # {type, count=1, at=20, duration=None}

    trust_weights: Optional[Dict[str, float]] = None

    detector_mode: str = "hybrid"           # hybrid | rules | model | none

    trust_enabled: bool = True

    ledger: str = "blockchain"              # blockchain | centralized

    speed_steps: int = 1



    @classmethod

    def from_dict(cls, d: Dict) -> "ExperimentSpec":

        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}

        return cls(**known)





def _safe_mean(values: List[float]) -> Optional[float]:

    values = [v for v in values if v is not None]

    return sum(values) / len(values) if values else None





def run_once(spec: ExperimentSpec, rep: int = 0) -> Dict[str, Any]:

    from backend.orchestrator import SimulationOrchestrator

    from simulation.scenarios.presets import ScheduledAttack



    cfg = get_config()

    orch = SimulationOrchestrator(cfg)

    orch.record_replay = False

    orch.persist_runs = False

    orch.ledger_mode = spec.ledger

    orch.trust_enabled = spec.trust_enabled

    orch.detector.mode = spec.detector_mode

    if spec.trust_weights:

        orch.trust_weights = spec.trust_weights

    orch.setup(spec.scenario)

    orch.rng = random.Random(1000 + rep)

    orch.attacks.rng = random.Random(2000 + rep)

    orch.scenario.attacks = [ScheduledAttack(a.get("at", 20), a["type"], a.get("count", 1)) for a in spec.attacks]

    stop_after = {a["type"]: a.get("duration") for a in spec.attacks if a.get("duration")}

    orch.start()



    t0 = time.time()

    steps = int(spec.duration / cfg.simulation.step_length)

    for _ in range(steps):

        orch.step()

        for vid, atk in list(orch.attacks.active.items()):

            limit = stop_after.get(atk.attack_type)

            if limit and orch.sim_time - atk.started_at >= limit:

                orch.stop_attack(vid)

    wall = time.time() - t0



    stats = orch.get_stats()

    perf = orch.get_performance()

    sec = stats["security"]

    attackers = set(orch.attack_reports)

    tp, fp, fn = sec["true_positives"], sec["false_positives"], sec["false_negatives"]

    honest_trust = [orch.trust.score(v) for v in orch.vehicle_states if v not in attackers]

    attacker_trust = [orch.trust.score(v) for v in attackers if v in orch.trust.scores]



    # tamper test: an insider rewrites a committed misbehaviour record; does the ledger notice?

    tamper_detected = None

    for block in orch.chain.chain[1:]:

        if block.transactions:

            block.transactions[0].data = {**block.transactions[0].data, "tampered": True}

            tamper_detected = not orch.chain.validate_chain()

            break



    result = {

        "detection_rate": sec["detection_rate"],

        "precision": sec["precision"],

        "f1": (2 * tp / (2 * tp + fp + fn)) if tp else 0.0,

        "false_positive_rate": sec["false_positive_rate"],

        "accuracy": sec["accuracy"],

        "malicious_acceptance_rate": perf["security_impact"]["malicious_acceptance_rate"],

        "honest_rejection_rate": perf["security_impact"]["honest_rejection_rate"],

        "detection_latency_s": perf["ai"]["detection_latency_avg_s"],

        "isolation_time_s": perf["ai"]["isolation_time_avg_s"],

        "attackers_isolated": (sum(1 for v in attackers if orch.attack_reports[v].get("blacklisted_at") is not None)

                               / len(attackers)) if attackers else None,

        "innocents_blacklisted": sum(1 for v in orch.trust.events

                                     if v not in attackers and any(e.kind == "blacklist" for e in orch.trust.events[v])),

        "avg_trust_honest": _safe_mean(honest_trust),

        "avg_trust_attackers": _safe_mean(attacker_trust),

        "bc_tx_latency_s": perf["blockchain"]["avg_tx_latency_s"],

        "bc_tps": perf["blockchain"]["tps"],

        "bc_storage_bytes": perf["blockchain"]["storage_bytes"],

        "tamper_detected": tamper_detected,

        "v2x_pdr": perf["v2x"]["pdr"],

        "v2x_latency_ms": perf["v2x"]["latency_avg_ms"],

        "inference_ms": perf["ai"]["inference_avg_ms"],

        "wall_time_s": wall,

        "per_attack": sec["attack_distribution"],

        "messages": stats["communication"]["messages_sent"],

        "vehicles_seen": stats["vehicles"]["total_registered"],

        "mock_mode": orch.mock_mode,

    }

    orch.shutdown()

    return result





def run_spec(spec: ExperimentSpec) -> Dict[str, Any]:

    logger.info("▶ %s (%s, %ss x%d, detector=%s, trust=%s, ledger=%s)", spec.name, spec.scenario, spec.duration,

                spec.repetitions, spec.detector_mode, spec.trust_enabled, spec.ledger)

    runs = [run_once(spec, rep) for rep in range(spec.repetitions)]

    summary = {}

    for k in METRIC_KEYS:

        vals = [r[k] for r in runs if isinstance(r[k], (int, float)) and not isinstance(r[k], bool)]

        bools = [r[k] for r in runs if isinstance(r[k], bool)]

        if vals:

            summary[k] = statistics.mean(vals)

            if len(vals) > 1:

                summary[k + "_std"] = statistics.stdev(vals)

        elif bools:

            summary[k] = all(bools)

        else:

            summary[k] = None

    return {"spec": asdict(spec), "summary": summary, "runs": runs}





def load_spec(name_or_path: str) -> List[ExperimentSpec]:

    """A YAML file defines one experiment, or several via `variants` (each overriding the base)."""

    path = name_or_path

    if not os.path.exists(path):

        path = os.path.join(get_config().experiment.configs_dir, f"{name_or_path}.yaml")

    with open(path) as fh:

        data = yaml.safe_load(fh)

    variants = data.pop("variants", None)

    if not variants:

        return [ExperimentSpec.from_dict(data)]

    return [ExperimentSpec.from_dict({**data, **v, "name": v.get("name", data.get("name"))}) for v in variants]





def list_configs() -> List[Dict[str, Any]]:

    cfg_dir = get_config().experiment.configs_dir

    out = []

    for f in sorted(os.listdir(cfg_dir)):

        if f.endswith(".yaml") and not f.startswith("._"):

            with open(os.path.join(cfg_dir, f)) as fh:

                d = yaml.safe_load(fh)

            out.append({"id": f[:-5], "name": d.get("name", f[:-5]), "description": d.get("description", ""),

                        "variants": [v.get("name") for v in d.get("variants", [])]})

    return out





def save_results(title: str, results: List[Dict[str, Any]], out_root: Optional[str] = None) -> str:

    out_root = out_root or get_config().experiment.results_dir

    out_dir = os.path.join(out_root, time.strftime("%Y%m%d-%H%M%S") + "_" + title.replace(" ", "_"))

    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "results.json"), "w") as fh:

        json.dump({"title": title, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results}, fh, indent=2, default=str)

    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as fh:

        w = csv.writer(fh)

        w.writerow(["experiment"] + METRIC_KEYS)

        for r in results:

            w.writerow([r["spec"]["name"]] + [r["summary"].get(k) for k in METRIC_KEYS])

    return out_dir





def print_table(results: List[Dict[str, Any]]):

    cols = ["detection_rate", "precision", "false_positive_rate", "malicious_acceptance_rate",

            "detection_latency_s", "isolation_time_s", "bc_tx_latency_s", "tamper_detected"]

    try:

        from rich.console import Console

        from rich.table import Table

        t = Table(title="Experiment results")

        t.add_column("experiment")

        for c in cols:

            t.add_column(c, justify="right")

        for r in results:

            t.add_row(r["spec"]["name"], *[_fmt(r["summary"].get(c)) for c in cols])

        Console(width=200).print(t)

    except ImportError:  # pragma: no cover

        for r in results:

            print(r["spec"]["name"], {c: _fmt(r["summary"].get(c)) for c in cols})





def _fmt(v) -> str:

    if v is None:

        return "—"

    if isinstance(v, bool):

        return "yes" if v else "no"

    if isinstance(v, float):

        return f"{v:.4f}" if abs(v) < 10 else f"{v:.1f}"

    return str(v)





def main(argv=None):

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)

    g = parser.add_mutually_exclusive_group(required=True)

    g.add_argument("--config", help="config name in experiments/configs (without .yaml) or a path")

    g.add_argument("--all", action="store_true", help="run every config")

    g.add_argument("--suite", choices=["baselines", "ablation"])

    parser.add_argument("--duration", type=float, help="override simulated seconds per run")

    parser.add_argument("--repetitions", type=int, help="override repetitions")

    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    for noisy in ("backend.orchestrator", "simulation", "ai.misbehavior_detector"):

        logging.getLogger(noisy).setLevel(logging.ERROR)



    if args.suite == "baselines":

        from experiments.baseline_comparison import baseline_specs

        specs, title = baseline_specs(), "baselines"

    elif args.suite == "ablation":

        from experiments.ablation_study import ablation_specs

        specs, title = ablation_specs(), "ablation"

    elif args.all:

        specs = [s for c in list_configs() for s in load_spec(c["id"])]

        title = "all"

    else:

        specs, title = load_spec(args.config), os.path.basename(args.config).replace(".yaml", "")

    for s in specs:

        if args.duration:

            s.duration = args.duration

        if args.repetitions:

            s.repetitions = args.repetitions



    results = [run_spec(s) for s in specs]

    out = save_results(title, results)

    print_table(results)

    logger.info("results written to %s", out)

    return out





if __name__ == "__main__":

    main()
