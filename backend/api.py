"""

FastAPI backend for the V2X trust framework.



Run from the repository root:

    uvicorn backend.api:app --host 127.0.0.1 --port 8000

"""



import sys

import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))



import asyncio

import glob

import json

import logging

import subprocess

import threading

import time

from contextlib import asynccontextmanager

from typing import Any, Dict, List, Optional



import orjson

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Path, Query

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse

from pydantic import BaseModel, Field



from config import get_config

from ai.misbehavior_detector import load_metrics

from backend.database import Database

from backend.evidence import evidence_hash

from backend.models import SimulationConfigRequest

from backend.orchestrator import SimulationOrchestrator

from backend.websocket import ConnectionManager

from blockchain.smart_contract import vehicle_hash

from simulation.attacks import ATTACK_TYPES

from simulation.scenarios.presets import list_scenarios, SCENARIOS



logger = logging.getLogger(__name__)

logging.basicConfig(level=get_config().log_level)



config = get_config()

db = Database(config.backend.database_url)

telemetry_ws = ConnectionManager()

events_ws = ConnectionManager()

orchestrator = SimulationOrchestrator(config)



running_event = threading.Event()

worker_thread: Optional[threading.Thread] = None





class ORJSONResponse(JSONResponse):

    media_type = "application/json"



    def render(self, content: Any) -> bytes:

        return orjson.dumps(content, option=orjson.OPT_NON_STR_KEYS)





def simulation_worker(loop: asyncio.AbstractEventLoop, queue: asyncio.Queue):

    period = 1.0 / config.backend.ws_broadcast_rate

    while running_event.is_set():

        t0 = time.perf_counter()

        try:

            snapshot = orchestrator.step()

            events = orchestrator.drain_events()

            loop.call_soon_threadsafe(queue.put_nowait, (snapshot, events))

        except Exception:

            logger.exception("Simulation step failed")

        time.sleep(max(0.0, period - (time.perf_counter() - t0)))





async def broadcast_worker(queue: asyncio.Queue):

    last_db = time.time()

    while True:

        snapshot, events = await queue.get()

        while queue.qsize() > 2:  # drop stale frames if clients are slow

            snapshot, more = queue.get_nowait()

            events += more

        await telemetry_ws.broadcast({"type": "telemetry", "data": snapshot})

        for ev in events:

            await telemetry_ws.broadcast(ev)

            await events_ws.broadcast(ev)

        if time.time() - last_db >= 1.0:

            last_db = time.time()

            try:

                await db.write_pipeline_batch(orchestrator.run_id, orchestrator.drain_db_queue())

            except Exception:

                logger.exception("DB write failed")





@asynccontextmanager

async def lifespan(app: FastAPI):

    global worker_thread

    await db.init_db()

    await asyncio.to_thread(orchestrator.setup)

    orchestrator.start()

    queue: asyncio.Queue = asyncio.Queue()

    running_event.set()

    worker_thread = threading.Thread(target=simulation_worker, args=(asyncio.get_running_loop(), queue), daemon=True)

    worker_thread.start()

    broadcaster = asyncio.create_task(broadcast_worker(queue))

    yield

    running_event.clear()

    if worker_thread:

        worker_thread.join(timeout=2.0)

    broadcaster.cancel()

    orchestrator.shutdown()





app = FastAPI(title="V2X AI + Blockchain Trust Framework API", lifespan=lifespan, default_response_class=ORJSONResponse)

app.add_middleware(

    CORSMiddleware,

    allow_origins=config.backend.cors_origins,

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





def _require_vehicle(vid: str) -> Dict:

    detail = orchestrator.vehicle_detail(vid)

    if detail is None:

        raise HTTPException(status_code=404, detail="Vehicle not found")

    return detail





# ---------------------------------------------------------------- simulation

class SpeedRequest(BaseModel):

    factor: int = Field(1, ge=1, le=10)





class ScenarioRequest(BaseModel):

    scenario_id: Optional[str] = None





@app.get("/api/health")

async def health():

    return {"status": "ok", "run_id": orchestrator.run_id, "mock_mode": orchestrator.mock_mode}





@app.get("/api/simulation/status")

async def simulation_status():

    snap = orchestrator.get_state_snapshot()

    return {k: snap[k] for k in ("simulation_running", "paused", "speed", "sim_time", "scenario", "mock_mode", "vehicle_count")} | {"run_id": orchestrator.run_id}





@app.post("/api/simulation/start")

async def start_simulation():

    orchestrator.start()

    return {"status": "started"}





@app.post("/api/simulation/pause")

async def pause_simulation():

    orchestrator.pause()

    return {"status": "paused"}





@app.post("/api/simulation/resume")

async def resume_simulation():

    orchestrator.resume()

    return {"status": "running"}





@app.post("/api/simulation/stop")

async def stop_simulation():

    orchestrator.stop()

    return {"status": "stopped"}





@app.post("/api/simulation/restart")

async def restart_simulation(req: Optional[ScenarioRequest] = None):

    scenario_id = req.scenario_id if req else None

    if scenario_id and scenario_id not in SCENARIOS:

        raise HTTPException(status_code=404, detail="Unknown scenario")

    await asyncio.to_thread(orchestrator.restart, scenario_id)

    return {"status": "restarted", "scenario": orchestrator.scenario.id, "run_id": orchestrator.run_id}





@app.post("/api/simulation/speed")

async def set_speed(req: SpeedRequest):

    orchestrator.set_speed(req.factor)

    return {"speed": orchestrator.speed}





@app.post("/api/simulation/config")

async def update_simulation_config(cfg: SimulationConfigRequest):

    if cfg.num_vehicles is not None:

        config.simulation.num_vehicles = cfg.num_vehicles

    if cfg.duration is not None:

        config.simulation.sim_duration = cfg.duration

    if cfg.scenario:

        if cfg.scenario not in SCENARIOS:

            raise HTTPException(status_code=404, detail="Unknown scenario")

        await asyncio.to_thread(orchestrator.restart, cfg.scenario)

    return {"status": "config updated"}





@app.get("/api/scenarios")

async def scenarios():

    return {"current": orchestrator.scenario.id, "scenarios": list_scenarios()}





@app.post("/api/scenario/load")

async def load_scenario(req: ScenarioRequest):

    if not req.scenario_id or req.scenario_id not in SCENARIOS:

        raise HTTPException(status_code=404, detail="Unknown scenario")

    await asyncio.to_thread(orchestrator.restart, req.scenario_id)

    return {"status": "loaded", "scenario": req.scenario_id, "run_id": orchestrator.run_id}





# ---------------------------------------------------------------- experiments

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

experiment_jobs: Dict[str, Dict[str, Any]] = {}





class ExperimentStart(BaseModel):

    config: Optional[str] = None      # config id in experiments/configs

    suite: Optional[str] = None       # "baselines" | "ablation"

    duration: Optional[float] = None

    repetitions: Optional[int] = None





@app.get("/api/experiments/configs")

async def experiment_configs():

    from experiments.experiment_runner import list_configs

    return {"configs": list_configs(), "suites": ["baselines", "ablation"]}





@app.post("/api/experiment/start")

async def start_experiment(req: ExperimentStart):

    """Runs the experiment in a separate process (its own SUMO instance) and records the output."""

    if not req.config and not req.suite:

        raise HTTPException(status_code=400, detail="config or suite required")

    if any(j["status"] == "running" for j in experiment_jobs.values()):

        raise HTTPException(status_code=409, detail="An experiment is already running")

    args = [sys.executable, "-m", "experiments.experiment_runner"]

    args += ["--suite", req.suite] if req.suite else ["--config", req.config]

    if req.duration:

        args += ["--duration", str(req.duration)]

    if req.repetitions:

        args += ["--repetitions", str(req.repetitions)]

    job_id = f"job-{int(time.time())}"

    log_path = os.path.join(ROOT, "experiments", "results", f"{job_id}.log")

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    log = open(log_path, "w")

    env = {**os.environ, "PYTHONUNBUFFERED": "1", "COLUMNS": "200"}

    proc = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)

    experiment_jobs[job_id] = {"id": job_id, "target": req.suite or req.config, "status": "running",

                               "started": time.time(), "proc": proc, "log": log_path}

    return {"job_id": job_id}





@app.get("/api/experiments/jobs")

async def experiment_job_list():

    out = []

    for j in experiment_jobs.values():

        if j["status"] == "running" and j["proc"].poll() is not None:

            j["status"] = "done" if j["proc"].returncode == 0 else "failed"

        try:

            with open(j["log"]) as fh:

                tail = [line for line in fh.read().splitlines() if "Retrying" not in line][-12:]

        except OSError:

            tail = []

        out.append({k: v for k, v in j.items() if k != "proc"} | {"log_tail": tail})

    return sorted(out, key=lambda j: -j["started"])





@app.get("/api/experiments/results")

async def experiment_results():

    rows = []

    for path in sorted(glob.glob(os.path.join(ROOT, "experiments", "results", "*", "results.json")), reverse=True):

        try:

            with open(path) as fh:

                data = json.load(fh)

        except (OSError, ValueError):

            continue

        rows.append({"id": os.path.basename(os.path.dirname(path)), "title": data.get("title"), "created": data.get("created"),

                     "experiments": [r["spec"]["name"] for r in data.get("results", [])]})

    return rows





@app.get("/api/experiments/results/{result_id}")

async def experiment_result(result_id: str):

    path = os.path.join(ROOT, "experiments", "results", os.path.basename(result_id), "results.json")

    if not os.path.exists(path):

        raise HTTPException(status_code=404, detail="Result not found")

    with open(path) as fh:

        data = json.load(fh)

    return data





# ------------------------------------------------------------------- replay

@app.get("/api/runs")

async def list_runs():

    runs = []

    for path in glob.glob(os.path.join(ROOT, "data", "runs", "*.meta.json")):

        try:

            with open(path) as fh:

                meta = json.load(fh)

        except (OSError, ValueError):

            continue

        meta["current"] = meta["run_id"] == orchestrator.run_id

        runs.append(meta)

    return sorted(runs, key=lambda r: -r.get("started_at", 0))





@app.get("/api/runs/{run_id}/frames")

async def run_frames(run_id: str, start: float = 0.0, end: float = 1e12, max_frames: int = Query(2400, le=10000)):

    if run_id == orchestrator.run_id:

        frames = orchestrator.replay_frames(start, end)

    else:

        path = os.path.join(ROOT, "data", "runs", f"{os.path.basename(run_id)}.jsonl")

        if not os.path.exists(path):

            raise HTTPException(status_code=404, detail="Run not found")

        frames = []

        with open(path) as fh:

            for line in fh:

                try:

                    f = json.loads(line)

                except ValueError:

                    continue

                if start <= f["t"] <= end:

                    frames.append(f)

    stride = max(1, len(frames) // max_frames + (1 if len(frames) % max_frames else 0)) if len(frames) > max_frames else 1

    return {"run_id": run_id, "total": len(frames), "stride": stride, "frames": frames[::stride]}





@app.get("/api/runs/{run_id}/alerts")

async def run_alerts(run_id: str):

    if run_id == orchestrator.run_id:

        with orchestrator.lock:

            return list(orchestrator.alerts)

    return (await db.get_alerts(run_id, 2000))[::-1]





# -------------------------------------------------------------- performance

@app.get("/api/performance")

async def performance():

    with orchestrator.lock:

        timeline = list(orchestrator.timeline)

    return {**orchestrator.get_performance(), "timeline": timeline}





# ------------------------------------------------------------------ vehicles

@app.get("/api/vehicles")

async def get_vehicles():

    return orchestrator.get_state_snapshot().get("vehicles", [])





@app.get("/api/vehicles/{vehicle_id}")

async def get_vehicle_detail(vehicle_id: str = Path(...)):

    return _require_vehicle(vehicle_id)





@app.get("/api/vehicles/{vehicle_id}/messages/received")

async def get_received(vehicle_id: str, filter: str = Query("all", pattern="^(all|valid|suspicious|malicious|emergency)$"),

                       sender: Optional[str] = None, type: Optional[str] = None,

                       time_from: Optional[float] = Query(None, alias="from"), time_to: Optional[float] = Query(None, alias="to"),

                       limit: int = Query(200, le=2000), privacy: bool = False):

    _require_vehicle(vehicle_id)

    return orchestrator.received_messages(vehicle_id, filter, sender, type, time_from, time_to, limit, privacy)





@app.get("/api/vehicles/{vehicle_id}/messages/sent")

async def get_sent(vehicle_id: str, filter: str = Query("all", pattern="^(all|valid|suspicious|malicious|emergency)$"),

                   type: Optional[str] = None, limit: int = Query(200, le=1000), privacy: bool = False):

    _require_vehicle(vehicle_id)

    return {"vehicle_id": vehicle_id, "messages": orchestrator.sent_messages(vehicle_id, filter, type, limit, privacy)}





@app.get("/api/vehicles/{vehicle_id}/trust")

async def get_vehicle_trust(vehicle_id: str):

    detail = _require_vehicle(vehicle_id)

    return {"vehicle_id": vehicle_id, "score": detail["trust_score"], "status": detail["status"],

            "components": detail["trust_components"], "weights": detail["trust_weights"],

            "history": orchestrator.trust.history(vehicle_id)}





@app.get("/api/vehicles/{vehicle_id}/trust/history")

async def get_trust_history(vehicle_id: str):

    _require_vehicle(vehicle_id)

    with orchestrator.lock:

        return {"vehicle_id": vehicle_id, "history": orchestrator.trust.history(vehicle_id)}





@app.get("/api/vehicles/{vehicle_id}/history")

async def get_vehicle_history(vehicle_id: str):

    return await get_trust_history(vehicle_id)





@app.get("/api/vehicles/{vehicle_id}/attacks")

async def get_vehicle_attacks(vehicle_id: str):

    detail = _require_vehicle(vehicle_id)

    with orchestrator.lock:

        evidence = orchestrator.evidence.for_vehicle(vehicle_id)

        reports = orchestrator.reports.recent_reports(vehicle_id, 50)

    return {"vehicle_id": vehicle_id, "detections": detail["attack_types"], "evidence": evidence[::-1],

            "attack_report": orchestrator.attack_comparison(vehicle_id), "neighbour_reports": reports}





@app.get("/api/vehicles/{vehicle_id}/blockchain")

async def get_vehicle_blockchain(vehicle_id: str):

    _require_vehicle(vehicle_id)

    vh = vehicle_hash(vehicle_id)

    with orchestrator.lock:

        out = []

        for block in orchestrator.chain.chain:

            for tx in block.transactions:

                if tx.vehicle_hash == vh:

                    out.append({"block": block.index, "confirmed": True, **tx.to_dict()})

        out += [{"block": None, "confirmed": False, **tx.to_dict()}

                for tx in orchestrator.chain.pending_transactions if tx.vehicle_hash == vh]

    return {"vehicle_id": vehicle_id, "vehicle_hash": vh, "transactions": out[::-1]}





# ------------------------------------------------------------------- attacks

class LaunchRequest(BaseModel):

    attack_type: str

    vehicle_id: Optional[str] = None

    params: Dict[str, Any] = Field(default_factory=dict)





class StopRequest(BaseModel):

    vehicle_id: Optional[str] = None





@app.get("/api/attacks/types")

async def attack_types():

    return [{"id": k, **v} for k, v in ATTACK_TYPES.items()]





@app.post("/api/attacks/launch")

async def launch_attack(req: LaunchRequest):

    try:

        return orchestrator.launch_attack(req.vehicle_id, req.attack_type, req.params)

    except ValueError as e:

        raise HTTPException(status_code=400, detail=str(e))





@app.post("/api/attacks/stop")

async def stop_attack(req: StopRequest):

    with orchestrator.lock:

        if req.vehicle_id:

            return {"stopped": [req.vehicle_id] if orchestrator.stop_attack(req.vehicle_id) else []}

        ids = list(orchestrator.attacks.active)

        orchestrator.attacks.stop_all(orchestrator.sim_time)

        return {"stopped": ids}





@app.get("/api/attacks/active")

async def active_attacks():

    with orchestrator.lock:

        return orchestrator.attacks.list_active()





@app.get("/api/attacks/history")

async def attack_history():

    with orchestrator.lock:

        return {"history": list(orchestrator.attacks.history),

                "reports": [orchestrator.attack_comparison(v) for v in orchestrator.attack_reports]}





@app.get("/api/attacks/{vehicle_id}/comparison")

async def attack_comparison(vehicle_id: str):

    comp = orchestrator.attack_comparison(vehicle_id)

    if comp is None:

        raise HTTPException(status_code=404, detail="No attack launched on this vehicle")

    return comp





# ------------------------------------------------------- evidence / alerts

@app.get("/api/evidence")

async def list_evidence(attack_type: Optional[str] = None, limit: int = Query(100, le=1000), privacy: bool = False):

    with orchestrator.lock:

        items = orchestrator.evidence.list(limit, attack_type)

        return [orchestrator.mask(e) for e in items] if privacy else items





@app.get("/api/evidence/{attack_id}")

async def get_evidence(attack_id: str, tamper: bool = False, privacy: bool = False):

    with orchestrator.lock:

        record = orchestrator.evidence.get(attack_id)

        if record is None:

            raise HTTPException(status_code=404, detail="Evidence not found")

        candidate = dict(record)

        if tamper:  # demonstrate tamper detection: modify the stored record and re-verify

            candidate["ai_probability"] = round(candidate["ai_probability"] * 0.5, 4)

            candidate["observed"] = "(tampered) " + str(candidate["observed"])

        verification = orchestrator.contract.verify_evidence(attack_id, evidence_hash(candidate))

    return {"record": orchestrator.mask(candidate) if privacy else candidate, "verification": verification, "tampered": tamper}





@app.get("/api/alerts")

async def get_alerts(limit: int = Query(100, le=500), severity: Optional[str] = None):

    with orchestrator.lock:

        alerts = list(orchestrator.alerts)

    if severity:

        alerts = [a for a in alerts if a["severity"] == severity]

    return alerts[-limit:][::-1]





@app.get("/api/events")

async def get_events():

    return await get_alerts(100)





@app.get("/api/events/recent")

async def get_recent_events():

    return await get_alerts(10)





# ------------------------------------------------------ analytics & graphs

@app.get("/api/stats")

async def get_stats():

    return orchestrator.get_stats()





@app.get("/api/timeline")

async def get_timeline():

    with orchestrator.lock:

        return list(orchestrator.timeline)





@app.get("/api/graph")

async def get_graph(min_messages: int = Query(1, ge=1)):

    return orchestrator.comm_graph(min_messages)





@app.post("/api/graph/reset")

async def reset_graph():

    orchestrator.reset_graph()

    return {"status": "reset"}





@app.get("/api/metrics")

async def get_metrics():

    stats = orchestrator.get_stats()

    offline = load_metrics(config.ai.model_dir) or {}

    best = next((m for m in offline.get("models", []) if m["model"] == offline.get("selected_model")), {})

    sec, com, bc = stats["security"], stats["communication"], stats["blockchain"]

    return {

        "ai_metrics": {"model": stats["ai"]["model"], "accuracy": best.get("accuracy"), "f1_score": best.get("macro_f1"),

                       "inference_time_ms": stats["ai"]["avg_inference_ms"],

                       "online_detection_rate": sec["detection_rate"], "online_precision": sec["precision"],

                       "online_false_positive_rate": sec["false_positive_rate"]},

        "trust_metrics": {"avg_trust": stats["vehicles"]["avg_trust"], "false_positives": sec["false_positives"],

                          "blacklisted": sec["blacklisted"]},

        "blockchain_metrics": {"tps": bc["tps"], "avg_block_time": bc["block_interval_s"],

                               "avg_tx_latency_s": bc["avg_tx_latency_s"], "storage_bytes": bc["storage_bytes"]},

        "v2x_metrics": {"msg_rate": com["messages_per_sec"], "latency_ms": com["avg_latency_ms"], "pdr": com["pdr"],

                        "throughput_kbps": com["throughput_kbps"]},

        "simulation_metrics": {"sim_time": orchestrator.sim_time, "speed": orchestrator.speed},

    }





@app.get("/api/ai/metrics")

async def ai_metrics():

    with orchestrator.lock:

        live_cm = {k: dict(v) for k, v in orchestrator.confusion_matrix.items()}

        per_attack = {k: dict(v) for k, v in orchestrator.per_attack.items()}

        info = orchestrator.detector.info()

        importances = orchestrator.detector.feature_importances

    return {"offline": load_metrics(config.ai.model_dir), "live": {

        "detector": info, "confusion_matrix": live_cm, "per_attack": per_attack,

        "security": orchestrator.get_stats()["security"], "feature_importances": importances}}





# ------------------------------------------------------------------- trust

class WeightsRequest(BaseModel):

    alpha: float = Field(..., ge=0)

    beta: float = Field(..., ge=0)

    gamma: float = Field(..., ge=0)

    delta: float = Field(..., ge=0)





@app.get("/api/trust/weights")

async def get_weights():

    return orchestrator.trust.weights()





@app.post("/api/trust/weights")

async def set_weights(req: WeightsRequest):

    try:

        orchestrator.set_trust_weights(req.alpha, req.beta, req.gamma, req.delta)

    except ValueError as e:

        raise HTTPException(status_code=400, detail=str(e))

    return orchestrator.trust.weights()





@app.get("/api/trust/overview")

async def trust_overview():

    snap = orchestrator.get_state_snapshot()

    bins = [0] * 10

    for v in snap["vehicles"]:

        bins[min(9, int(v["trust_score"] * 10))] += 1

    with orchestrator.lock:

        recent = []

        for vid, events in orchestrator.trust.events.items():

            recent += [{"vehicle_id": vid, **e.__dict__} for e in events if e.kind not in ("init", "reward")]

    recent.sort(key=lambda e: -e["time"])

    return {"distribution": [{"range": f"{i / 10:.1f}-{(i + 1) / 10:.1f}", "count": c} for i, c in enumerate(bins)],

            "avg_trust": snap["stats"]["vehicles"]["avg_trust"], "weights": orchestrator.trust.weights(),

            "thresholds": {"trusted": orchestrator.trust.trusted_threshold, "malicious": orchestrator.trust.malicious_threshold,

                           "blacklist": orchestrator.contract.BLACKLIST_THRESHOLD},

            "blacklisted": list(orchestrator.trust.blacklisted), "recent_changes": recent[:50]}





# ---------------------------------------------------------------- identity

@app.get("/api/identity/stats")

async def identity_stats():

    reg = orchestrator.registry

    return {"enrolled": reg.count(), "crl_size": reg.crl_size(), "algorithm": "ECDSA P-256 / SHA-256",

            "pseudonym_lifetime_s": reg.pseudonym_lifetime, **reg.stats}





@app.get("/api/identity/revoked")

async def revoked_certificates():

    with orchestrator.lock:

        return orchestrator.registry.revoked_list()





@app.get("/api/identity/{vehicle_id}")

async def identity(vehicle_id: str):

    cert = orchestrator.registry.get(vehicle_id)

    if cert is None:

        raise HTTPException(status_code=404, detail="Unknown vehicle")

    return cert.public_view()





# -------------------------------------------------------------- blockchain

@app.get("/api/blockchain/status")

async def get_blockchain_status():

    with orchestrator.lock:

        perf = orchestrator.chain.performance(orchestrator.sim_time)

        valid = orchestrator.chain.validate_chain()

    return {"connected": True, **perf, "chain_valid": valid, "crl_size": orchestrator.registry.crl_size(),

            "latest_block_hash": perf["latest_hash"], "validator_ids": orchestrator.chain.validators}





def _block_view(block, full: bool = False) -> Dict:

    view = {"index": block.index, "hash": block.hash, "prev_hash": block.previous_hash, "timestamp": block.timestamp,

            "tx_count": len(block.transactions), "validator": block.validator, "merkle_root": block.merkle_root,

            "signature": orchestrator.chain.block_signatures.get(block.index, "")}

    if full:

        view["transactions"] = [tx.to_dict() for tx in block.transactions]

        view["signature_valid"] = orchestrator.chain.verify_block_signature(block)

        view["hash_valid"] = block.hash == block.compute_hash()

    return view





@app.get("/api/blockchain/blocks")

async def get_blocks(limit: int = Query(20, le=200), offset: int = 0):

    with orchestrator.lock:

        chain = orchestrator.chain.chain

        end = len(chain) - offset

        return [_block_view(b) for b in reversed(chain[max(0, end - limit):max(0, end)])]





@app.get("/api/blockchain/blocks/{index}")

async def get_block(index: int = Path(...)):

    with orchestrator.lock:

        if not 0 <= index < len(orchestrator.chain.chain):

            raise HTTPException(status_code=404, detail="Block not found")

        return _block_view(orchestrator.chain.chain[index], full=True)





@app.get("/api/blockchain/transactions")

async def get_transactions(limit: int = Query(50, le=500), tx_type: Optional[str] = None):

    out: List[Dict] = []

    with orchestrator.lock:

        for tx in reversed(orchestrator.chain.pending_transactions):

            if not tx_type or tx.tx_type.value == tx_type:

                out.append({"block": None, "confirmed": False, **tx.to_dict()})

        for block in reversed(orchestrator.chain.chain):

            for tx in reversed(block.transactions):

                if len(out) >= limit:

                    return out

                if not tx_type or tx.tx_type.value == tx_type:

                    out.append({"block": block.index, "confirmed": True, **tx.to_dict()})

    return out[:limit]





@app.get("/api/blockchain/transactions/{tx_id}")

async def get_transaction(tx_id: str):

    with orchestrator.lock:

        tx = orchestrator.chain.find_transaction(tx_id)

    if tx is None:

        raise HTTPException(status_code=404, detail="Transaction not found")

    return tx





@app.get("/api/blockchain/validate")

async def validate_chain():

    with orchestrator.lock:

        chain = orchestrator.chain

        bad_sigs = [b.index for b in chain.chain if not chain.verify_block_signature(b)]

        return {"chain_valid": chain.validate_chain(), "blocks": len(chain.chain), "invalid_signatures": bad_sigs}





# ------------------------------------------------------------------ network

@app.get("/api/network/status")

async def get_network_status():

    snap = orchestrator.get_state_snapshot()

    return {k: snap[k] for k in ("simulation_running", "sim_time", "vehicle_count", "trusted", "suspicious",

                                 "misbehaving", "messages_total", "blockchain_blocks", "blockchain_txs")}





@app.get("/api/network/geometry")

async def get_network_geometry():

    return orchestrator.network_geometry





@app.get("/api/history/db/alerts")

async def db_alerts(limit: int = Query(200, le=2000)):

    return await db.get_alerts(orchestrator.run_id, limit)





@app.get("/api/history/db/messages")

async def db_messages(vehicle_id: Optional[str] = None, limit: int = Query(500, le=5000)):

    return await db.get_message_log(orchestrator.run_id, vehicle_id, limit)





# ---------------------------------------------------------------- websockets

async def _hold(ws: WebSocket, manager: ConnectionManager):

    await manager.connect(ws)

    try:

        while True:

            await ws.receive_text()

    except WebSocketDisconnect:

        manager.disconnect(ws)





@app.websocket("/ws/telemetry")

async def ws_telemetry(websocket: WebSocket):

    await _hold(websocket, telemetry_ws)





@app.websocket("/ws/events")

async def ws_events(websocket: WebSocket):

    await _hold(websocket, events_ws)
