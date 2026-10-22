"""

Simulation orchestrator: runs the end-to-end pipeline every SUMO step.



    SUMO step -> enroll new vehicles / prune departed

    -> build CAM/DENM per vehicle -> AttackManager.transform -> sign

    -> V2X channel broadcast (range, loss, latency) + RSU transmitter localization

    -> misbehavior detection (rules + trained model) per message

    -> received-message history per receiver + neighbour reports

    -> reputation consensus -> dynamic trust update

    -> smart contract (reports, evidence hash, blacklist, rehabilitation)

    -> PoA blockchain sealing -> alerts / websocket events / DB rows



All public methods are thread-safe: the simulation loop runs in a worker

thread while the API reads snapshots and issues commands.

"""



import json

import logging

import math

import os

import random

import threading

import time

from collections import Counter, defaultdict, deque

from typing import Any, Deque, Dict, List, Optional, Tuple



from ai.misbehavior_detector import MisbehaviorDetector, FEATURE_NAMES

from backend.evidence import EvidenceStore

from blockchain.chain import PoABlockchain, CentralizedLedger

from blockchain.smart_contract import TrustManagementContract, vehicle_hash

from simulation.attacks import AttackManager, ATTACK_TYPES

from simulation.pedestrians import PedestrianModel

from simulation.road_network import EMERGENCY_TYPES, VEHICLE_TYPES

from simulation.scenarios.presets import get_scenario, DEFAULT_SCENARIO

from trust.reputation import ReportAggregator

from trust.trust_engine import DynamicTrustEngine, ATTACK_LABELS

from v2x.channel import V2XChannel

from v2x.factory import make_cam, make_denm, public_view, summarize, _next_id

from v2x.identity import IdentityRegistry, SIGNATURE_BYTES, CERTIFICATE_BYTES



logger = logging.getLogger(__name__)



BEACON_INTERVAL = 1.0        # CAM period in sim seconds

EMERGENCY_DENM_INTERVAL = 3.0

ALERT_COOLDOWN = 10.0

EVIDENCE_INTERVAL = 5.0

BLACKLISTED_REPORT_INTERVAL = 5.0

NOTIFY_INTERVAL = 10.0       # min seconds between RSU misbehaviour notifications per vehicle

RECORD_EVERY_STEPS = 5       # replay frame every 0.5 s of sim time

PAYLOAD_BYTES = {"CAM": 200, "DENM": 260, "VAM": 150}

RUNS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "runs")



try:

    import psutil

    _PROC = psutil.Process()

except Exception:  # pragma: no cover

    _PROC = None      # min seconds between evidence records per (vehicle, attack)

RECEIVED_BUFFER = 3000

SENT_BUFFER = 400





class MockSumoManager:

    """Fallback traffic model used when SUMO is unavailable: vehicles drive on a 4x4 grid."""



    TYPES = [("car", .44), ("suv", .14), ("taxi", .10), ("bus", .06), ("truck", .08),

             ("motorcycle", .09), ("ambulance", .03), ("firetruck", .02), ("police", .04)]



    def __init__(self, num_vehicles: int, grid: float = 200.0, n: int = 4, seed: int = 42):

        self.rng = random.Random(seed)

        self.grid, self.n = grid, n

        self.max = grid * (n - 1)

        self.vehicles: Dict[str, Dict] = {}

        self.arrived: List[str] = []

        self.t = 0.0

        for i in range(num_vehicles):

            self._spawn(f"m{i}")



    def _spawn(self, vid: str):

        r = self.rng

        horizontal = r.random() < 0.5

        line = r.randrange(self.n) * self.grid

        pos = r.uniform(0, self.max)

        heading = r.choice([90.0, 270.0]) if horizontal else r.choice([0.0, 180.0])

        vtype = r.choices([t for t, _ in self.TYPES], [w for _, w in self.TYPES])[0]

        self.vehicles[vid] = {

            "position": (pos, line) if horizontal else (line, pos), "speed": r.uniform(8, 13),

            "acceleration": 0.0, "heading": heading, "lane_id": "mock_0", "road_id": "mock",

            "vehicle_type": vtype, "vehicle_class": vtype, "route": [], "length": 4.5,

        }



    def step(self, dt: float = 0.1):

        self.t += dt

        self.arrived = []

        for vid, v in self.vehicles.items():

            x, y = v["position"]

            rad = math.radians(v["heading"])

            nx, ny = x + v["speed"] * dt * math.sin(rad), y + v["speed"] * dt * math.cos(rad)

            # turn at intersections occasionally, bounce at the border

            if any(abs(c % self.grid) < 0.7 for c in (nx, ny)) and self.rng.random() < 0.02:

                v["heading"] = (v["heading"] + self.rng.choice([90, -90])) % 360

            if not (0 <= nx <= self.max and 0 <= ny <= self.max):

                v["heading"] = (v["heading"] + 180) % 360

                nx, ny = min(max(nx, 0), self.max), min(max(ny, 0), self.max)

            new_speed = max(2.0, min(14.0, v["speed"] + self.rng.gauss(0, 0.2)))

            v["acceleration"] = (new_speed - v["speed"]) / dt

            v["speed"] = new_speed

            v["position"] = (nx, ny)

        return self.t



    def get_all_vehicle_states(self) -> Dict[str, Dict]:

        return {vid: dict(v) for vid, v in self.vehicles.items()}



    def stop(self):

        pass



    def is_finished(self) -> bool:

        return False





class SimulationOrchestrator:

    def __init__(self, config):

        self.config = config

        self.lock = threading.RLock()

        self.sumo = None

        self.mock_mode = True

        self.scenario = get_scenario(DEFAULT_SCENARIO)

        self.speed = 1              # sim steps per tick

        self.is_running = False

        self.paused = False

        self.rsus = [

            {"id": "RSU_1", "x": 150.0, "y": 150.0},

            {"id": "RSU_2", "x": 450.0, "y": 150.0},

            {"id": "RSU_3", "x": 150.0, "y": 450.0},

            {"id": "RSU_4", "x": 450.0, "y": 450.0},

            {"id": "RSU_5", "x": 300.0, "y": 300.0},

        ]

        self.network_geometry: Dict[str, Any] = {"bounds": {}, "edges": [], "junctions": []}

        self.detector = MisbehaviorDetector(None, model_dir=config.ai.model_dir)

        self.sample_sink: Optional[List] = None     # set by the training script to collect features

        self.force_mock = os.environ.get('V2X_MOCK_TRAFFIC') == '1'

        self.trust_weights = None

        # experiment switches

        self.trust_enabled = True               # False = "no trust management" baseline

        self.ledger_mode = "blockchain"         # or "centralized"

        self.pedestrian_count = 12

        self.record_replay = True               # keep replay frames in memory

        self.persist_runs = os.environ.get("V2X_PERSIST_RUNS", "1") == "1"   # ... and on disk (data/runs)

        self._reset_state()



    # ================================================================== lifecycle

    def _reset_state(self):

        seed = self.scenario.seed

        self.rng = random.Random(seed)

        self.registry = IdentityRegistry(pseudonym_lifetime=60.0)

        self.channel = V2XChannel(self.config.vehicle.communication_range, 500.0, seed=seed)

        self.attacks = AttackManager(seed=seed)

        self.detector.registry = self.registry

        self.detector.reset()

        self.trust = DynamicTrustEngine()

        if self.trust_weights:

            self.trust.set_weights(**self.trust_weights)

        self.reports = ReportAggregator(window=5.0)

        self.chain = (CentralizedLedger() if self.ledger_mode == "centralized"

                      else PoABlockchain([r["id"] for r in self.rsus], block_interval=2.0))

        self.contract = TrustManagementContract(self.chain, [r["id"] for r in self.rsus])

        self.evidence = EvidenceStore()



        self.run_id = time.strftime("run-%Y%m%d-%H%M%S") + f"-{random.randrange(1000):03d}"

        self.sim_time = 0.0

        self.step_count = 0

        self.vehicle_states: Dict[str, Dict] = {}

        self.vehicles: Dict[str, Dict] = {}          # per-vehicle info & counters (kept after departure)

        self.departed: Deque[str] = deque()

        self.received: Dict[str, Deque] = defaultdict(lambda: deque(maxlen=RECEIVED_BUFFER))

        self.sent: Dict[str, Deque] = defaultdict(lambda: deque(maxlen=SENT_BUFFER))

        self.rsu_stats = {r["id"]: {"received": 0, "flagged": 0, "blocks_sealed": 0} for r in self.rsus}

        self.edges: Dict[Tuple[str, str], Counter] = defaultdict(Counter)

        self.alerts: Deque[Dict] = deque(maxlen=500)

        self._alert_seq = 0

        self._last_alert: Dict[Tuple[str, str], float] = {}

        self._last_evidence: Dict[Tuple[str, str], float] = {}

        self._last_chain_report: Dict[str, float] = {}

        self.events_out: List[Dict] = []

        self.db_queue: Dict[str, List[Dict]] = {"trust": [], "evidence": [], "alerts": [], "messages": []}

        self.scenario_launched: set = set()

        self.attack_reports: Dict[str, Dict] = {}

        self.msg_times: Deque[float] = deque()

        self.counters = Counter()

        self.confusion = Counter()                     # tp / fp / fn / tn at message level

        self.per_attack = defaultdict(Counter)         # attack -> total / detected / correct_type

        self.confusion_matrix = defaultdict(Counter)   # true label -> predicted label

        self.timeline: Deque[Dict] = deque(maxlen=600)

        self._last_snapshot: Optional[Dict] = None

        self._proc_ms = 0.0

        self._last_timeline_t = -1e9

        self.pedestrians: Optional[PedestrianModel] = None

        self.ped_states: Dict[str, Dict] = {}

        self._last_notify: Dict[str, float] = {}

        self.perf = {k: deque(maxlen=n) for k, n in (("latency", 5000), ("e2e", 5000), ("infer", 3000),

                                                      ("step_ms", 1000), ("cpu", 600))}

        self._frames: Deque[Dict] = deque(maxlen=7200)

        self._frame_buffer: List[str] = []

        self._run_started = time.time()



    def setup(self, scenario_id: Optional[str] = None):

        with self.lock:

            if scenario_id:

                self.scenario = get_scenario(scenario_id)

            self._shutdown_sumo()

            self._reset_state()

            try:

                from simulation.sumo_manager import SumoManager, SUMO_AVAILABLE

                from simulation.scenarios.default_grid import DefaultGridScenario

                if self.force_mock:

                    raise RuntimeError("mock traffic forced (V2X_MOCK_TRAFFIC=1)")

                if not SUMO_AVAILABLE:

                    raise ImportError("SUMO tools not found")

                scen = DefaultGridScenario(self.scenario)

                scen.setup()

                gui_mode = self.config.simulation.sumo_binary == "sumo-gui"

                self.sumo = SumoManager(scen.get_config_path(), gui=gui_mode)

                self.network_geometry = scen.generator.parse_network_geometry(scen.net_file)

                self.sumo.start()

                self.mock_mode = False

                if gui_mode:

                    import traci

                    for rsu in self.rsus:

                        try:

                            traci.poi.add(rsu["id"], rsu["x"], rsu["y"], (0, 150, 255, 255), poiType="RSU", layer=10, width=5, height=5)

                        except Exception as e:

                            logger.warning(f"Could not add POI for {rsu['id']}: {e}")

                logger.info("Connected to SUMO (scenario %s)", self.scenario.id)

            except Exception as e:

                logger.warning("Using mock traffic model: %s", e)

                self.mock_mode = True

                self.sumo = MockSumoManager(num_vehicles=60, seed=self.scenario.seed)

                self.network_geometry = self._mock_geometry()

            if self.pedestrian_count:

                self.pedestrians = PedestrianModel(self.network_geometry, self.pedestrian_count, seed=self.scenario.seed)

                for pid in self.pedestrians.peds:

                    self.registry.enroll(pid, "pedestrian", "pedestrian", 0.0)

            self._write_run_meta()



    def _mock_geometry(self) -> Dict[str, Any]:

        edges = []

        for i in range(4):

            c = i * 200.0

            edges.append({"id": f"h{i}", "shape": [(0.0, c), (600.0, c)], "lanes": 2})

            edges.append({"id": f"v{i}", "shape": [(c, 0.0), (c, 600.0)], "lanes": 2})

        junctions = [{"id": f"j{i}{j}", "coord": (i * 200.0, j * 200.0), "type": "traffic_light"} for i in range(4) for j in range(4)]

        return {"bounds": {"min_x": 0, "min_y": 0, "max_x": 600, "max_y": 600}, "edges": edges,

                "junctions": junctions, "traffic_lights": []}



    def _shutdown_sumo(self):

        self._flush_frames(final=True)

        if self.sumo is not None:

            try:

                self.sumo.stop()

            except Exception:

                pass

        self.sumo = None



    def start(self):

        with self.lock:

            if self.sumo is None:

                self.setup()

            self.is_running = True

            self.paused = False



    def pause(self):

        with self.lock:

            self.paused = True



    def resume(self):

        with self.lock:

            self.paused = False

            self.is_running = True



    def stop(self):

        with self.lock:

            self.is_running = False

            self.paused = False



    def shutdown(self):

        with self.lock:

            self.is_running = False

            self._shutdown_sumo()



    def restart(self, scenario_id: Optional[str] = None):

        with self.lock:

            self.setup(scenario_id or self.scenario.id)

            self.is_running = True

            self.paused = False



    def set_speed(self, factor: int):

        with self.lock:

            self.speed = max(1, min(10, int(factor)))



    def set_trust_weights(self, alpha: float, beta: float, gamma: float, delta: float):

        with self.lock:

            self.trust.set_weights(alpha, beta, gamma, delta)

            self.trust_weights = self.trust.weights()



    # ==================================================================== attacks

    def launch_attack(self, vehicle_id: Optional[str], attack_type: str, params: Optional[Dict] = None) -> Dict:

        with self.lock:

            if attack_type not in ATTACK_TYPES:

                raise ValueError(f"Unknown attack type '{attack_type}'")

            if not vehicle_id:

                vehicle_id = self._pick_attacker()

                if not vehicle_id:

                    raise ValueError("No eligible vehicle available")

            if vehicle_id not in self.vehicle_states:

                raise ValueError(f"Vehicle {vehicle_id} is not active")

            if attack_type == "collusion":

                return self._launch_collusion(vehicle_id, params or {})

            attack = self.attacks.launch(vehicle_id, attack_type, self.sim_time, params)

            self._init_attack_report(vehicle_id, attack_type)

            self._alert("info", "attack_launched", vehicle_id, f"Attack launched: {ATTACK_TYPES[attack_type]['label']}",

                        f"{ATTACK_TYPES[attack_type]['description']} (simulation control)",

                        {"attack_type": attack_type, "params": attack.to_dict()["params"]}, force=True)

            return attack.to_dict()



    def _init_attack_report(self, vehicle_id: str, attack_type: str):

        info = self.vehicles.get(vehicle_id, {})

        self.attack_reports[vehicle_id] = {

            "vehicle_id": vehicle_id, "attack_type": attack_type, "label": ATTACK_TYPES[attack_type]["label"],

            "launched_at": self.sim_time,

            "before": {"trust": self.trust.score(vehicle_id), "status": self.trust.status(vehicle_id),

                       "registered_type": info.get("type"), "claimed_type": info.get("claimed_type"),

                       "on_chain_reports": self.contract.on_chain_reports(vehicle_id)},

            "first_detection": None, "blacklisted_at": None, "evidence_ids": [], "tx_ids": [],

        }



    def _launch_collusion(self, leader: str, params: Dict) -> Dict:

        """Pick the leader plus the 2 nearest eligible vehicles; all report the same fake accident."""

        lx, ly = self.vehicle_states[leader]["position"]

        heading = math.radians(self.vehicle_states[leader].get("heading", 0.0))

        ev = (lx + 80 * math.sin(heading), ly + 80 * math.cos(heading))

        size = int(params.get("members", 3))

        others = sorted(

            (math.hypot(st["position"][0] - lx, st["position"][1] - ly), vid)

            for vid, st in self.vehicle_states.items()

            if vid != leader and self.vehicles[vid]["type"] not in EMERGENCY_TYPES

            and not self.attacks.is_attacker(vid) and vid not in self.trust.blacklisted)

        members = [leader] + [vid for d, vid in others[: size - 1] if d <= 350]

        if len(members) < 2:

            raise ValueError("Collusion needs at least 2 vehicles near each other")

        group = f"CG-{self.step_count}"

        for vid in members:

            self.attacks.launch(vid, "collusion", self.sim_time,

                                {"group": group, "members": members, "event_x": round(ev[0], 1), "event_y": round(ev[1], 1)})

            self._init_attack_report(vid, "collusion")

        self._alert("info", "attack_launched", leader, "Attack launched: Collusion",

                    f"Group {group}: {', '.join(members)} report a fake accident at ({ev[0]:.0f}, {ev[1]:.0f})",

                    {"attack_type": "collusion", "members": members}, force=True)

        return self.attacks.active[leader].to_dict()



    def stop_attack(self, vehicle_id: str) -> bool:

        with self.lock:

            return self.attacks.stop(vehicle_id, self.sim_time) is not None



    def _pick_attacker(self) -> Optional[str]:

        candidates = [vid for vid, v in self.vehicles.items()

                      if v["active"] and v["type"] not in EMERGENCY_TYPES and not self.attacks.is_attacker(vid)

                      and self.sim_time - v["first_seen"] >= 3.0 and vid not in self.trust.blacklisted]

        return self.rng.choice(sorted(candidates)) if candidates else None



    def attack_comparison(self, vehicle_id: str) -> Optional[Dict]:

        with self.lock:

            rep = self.attack_reports.get(vehicle_id)

            if not rep:

                return None

            info = self.vehicles.get(vehicle_id, {})

            out = dict(rep)

            out["after"] = {

                "trust": self.trust.score(vehicle_id), "status": self.trust.status(vehicle_id),

                "registered_type": info.get("type"), "claimed_type": info.get("claimed_type"),

                "on_chain_reports": self.contract.on_chain_reports(vehicle_id),

                "active": info.get("active", False),

                "attack_running": self.attacks.is_attacker(vehicle_id),

            }

            out["trust_timeline"] = [e for e in self.trust.history(vehicle_id) if e["time"] >= rep["launched_at"] - 5]

            return out



    # ======================================================================= step

    def step(self) -> Dict[str, Any]:

        with self.lock:

            if not self.is_running or self.paused or self.sumo is None:

                return self.get_state_snapshot()

            for _ in range(self.speed):

                t0 = time.perf_counter()

                self._sim_step()

                self.perf["step_ms"].append((time.perf_counter() - t0) * 1000)

            return self.get_state_snapshot(refresh=True)



    def _sim_step(self):

        dt = self.config.simulation.step_length

        if not self.mock_mode and self.sumo.is_finished():

            logger.info("Scenario finished - restarting")

            self.setup(self.scenario.id)

            self.is_running = True

        self.sumo.step()

        self.step_count += 1

        self.sim_time = round(self.step_count * dt, 2)

        now = self.sim_time



        states = self.sumo.get_all_vehicle_states()

        self._sync_vehicles(states, now)

        if self.pedestrians:

            self.pedestrians.step(dt)

            self.ped_states = self.pedestrians.states()

        self.channel.update_topology({vid: s["position"] for vid, s in states.items()}, self.rsus,

                                     {pid: p["position"] for pid, p in self.ped_states.items()})

        if self.step_count % 10 == 0 and _PROC is not None:

            self.perf["cpu"].append((now, _PROC.cpu_percent(None)))

        if self.step_count % RECORD_EVERY_STEPS == 0 and self.record_replay:

            self._record_frame(states, now)

        if self.step_count % 100 == 0:

            self.registry.rotate_pseudonyms(now)

        self._run_scenario_schedule(now)



        # ---- 1. build and transmit messages

        outgoing: List[Dict] = []

        for vid, st in states.items():

            info = self.vehicles[vid]

            due = (self.step_count + info["phase"]) % int(round(BEACON_INTERVAL / dt)) == 0

            if not self.attacks.beacon_due(vid, due):

                continue

            cert = self.registry.get(vid)

            cam = make_cam(vid, st, now, cert, self.rng)

            batch = [cam]

            batch += self._legit_denms(vid, st, cam, now)

            for msg in batch:

                produced = self.attacks.transform(msg, st, now, self.registry.sign) if msg is cam else \

                    [self._sign(msg)]

                outgoing.extend(produced)

            info["claimed_type"] = cam["claimed_type"]

            info["emergency_flag"] = cam["emergency_flag"]



        for pid, pst in self.ped_states.items():

            if (self.step_count + int(pid[1:])) % 10 == 0:

                vam = make_cam(pid, pst, now, self.registry.get(pid), self.rng, gps_std=2.0)

                vam["type"], vam["msg_id"] = "VAM", vam["msg_id"].replace("CAM", "VAM")

                outgoing.append(self._sign(vam))



        if not outgoing:

            self._seal_blocks(now)

            return



        items = []

        for msg in outgoing:

            items.append((msg, self.channel.localize_transmitter(msg["_tx_pos"])))

        t_det = time.perf_counter()

        results = self.detector.detect_batch(items, now)

        per_msg_ms = (time.perf_counter() - t_det) * 1000 / len(items)

        self.perf["infer"].append(per_msg_ms)

        self._proc_ms = per_msg_ms



        # ---- 2. deliver, record history, collect verdicts

        flagged: Dict[str, Tuple[Dict, Dict, Dict]] = {}

        clean = Counter()

        for (msg, loc), res in zip(items, results):

            self.attacks.capture(msg)

            self._account_ground_truth(msg, res, now)

            if self.sample_sink is not None:

                self.sample_sink.append(([res["features"][n] for n in FEATURE_NAMES], self._truth(msg, res) or "normal"))

            accused = self._attribute(msg, res, loc)

            record = self._make_record(msg, res, accused, now)

            size = PAYLOAD_BYTES.get(msg["type"], 200) + SIGNATURE_BYTES + CERTIFICATE_BYTES

            deliveries = self.channel.broadcast(msg["_tx"], msg["_tx_pos"], size, pedestrian=msg["type"] == "VAM")

            self._deliver(record, msg, res, accused, deliveries, now)

            if accused is None:

                continue

            if res["classification"] != "Normal":

                cur = flagged.get(accused)

                if cur is None or res["probability"] > cur[1]["probability"]:

                    flagged[accused] = (msg, res, record)

            elif msg["sender_id"] == accused:

                clean[accused] += 1



        # ---- 3. trust, contract, evidence, alerts

        for accused, (msg, res, record) in flagged.items():

            self._handle_detection(accused, msg, res, record, now)

        for vid, n in clean.items():

            if vid not in flagged:

                ev = self.trust.reward(vid, now, n)

                if ev:

                    self._queue_trust(vid, ev)

        if self.step_count % 10 == 0:

            self._check_rehabilitation(now)

            self.detector.prune(now)

        for lat in self.channel.drain_latency_samples():

            self.perf["latency"].append(lat)

            self.perf["e2e"].append(lat + self._proc_ms)

        self._seal_blocks(now)



    # ------------------------------------------------------------ vehicle sync

    def _sync_vehicles(self, states: Dict[str, Dict], now: float):

        for vid in list(self.vehicle_states):

            if vid not in states:

                self._on_departure(vid, now)

        for vid, st in states.items():

            if vid not in self.vehicles or not self.vehicles[vid]["active"]:

                self._on_arrival(vid, st, now)

            self.vehicles[vid]["last_seen"] = now

        self.vehicle_states = states



    def _on_arrival(self, vid: str, st: Dict, now: float):

        vtype = st.get("vehicle_type") or "car"

        if vtype not in VEHICLE_TYPES:

            vtype = "car"  # SUMO default type

        cert = self.registry.enroll(vid, vtype, st.get("vehicle_class", "passenger"), now)

        self.trust.ensure(vid, now)

        rsu = self._nearest_rsu(st["position"])

        tx = self.contract.register_vehicle(vid, cert.cert_id, vtype, self.trust.score(vid), rsu, now)

        self.vehicles[vid] = {

            "id": vid, "type": vtype, "vehicle_class": st.get("vehicle_class", ""), "claimed_type": vtype,

            "emergency_flag": vtype in EMERGENCY_TYPES, "first_seen": now, "last_seen": now, "active": True,

            "phase": self.rng.randrange(10), "sent": 0, "received": 0, "suspicious_sent": 0,

            "malicious_sent": 0, "detections": Counter(), "last_prob": 0.0, "registration_tx": tx.tx_id,

            "stopped_since": None, "last_denm": -99.0, "last_lane": st.get("lane_id"), "route": st.get("route", []),

            "blockchain_txs": [tx.tx_id],

        }

        self.counters["vehicles_registered"] += 1



    def _on_departure(self, vid: str, now: float):

        info = self.vehicles.get(vid)

        if info:

            info["active"] = False

            info["departed_at"] = now

        self.attacks.stop(vid, now)

        self.departed.append(vid)

        while len(self.departed) > 300:

            old = self.departed.popleft()

            if old in self.vehicles and not self.vehicles[old]["active"]:

                self.vehicles.pop(old, None)

                self.received.pop(old, None)

                self.sent.pop(old, None)

                self.trust.forget(old)

                self.reports.forget(old)



    def _nearest_rsu(self, pos) -> str:

        return min(self.rsus, key=lambda r: (r["x"] - pos[0]) ** 2 + (r["y"] - pos[1]) ** 2)["id"]



    def _sign(self, msg: Dict) -> Dict:

        msg["signature"] = self.registry.sign(msg["sender_id"], msg)

        return msg



    def _legit_denms(self, vid: str, st: Dict, cam: Dict, now: float) -> List[Dict]:

        info = self.vehicles[vid]

        out = []

        if info["type"] in EMERGENCY_TYPES and now - info["last_denm"] >= EMERGENCY_DENM_INTERVAL:

            info["last_denm"] = now

            out.append(make_denm(cam, "EMERGENCY_VEHICLE_APPROACH", (cam["x"], cam["y"]), 5,

                                 f"{info['type'].title()} on emergency run", now))

        speed = st.get("speed", 0.0)

        if speed < 0.3:

            info["stopped_since"] = info["stopped_since"] if info["stopped_since"] is not None else now

            if now - info["stopped_since"] > 15 and now - info["last_denm"] >= 10:

                info["last_denm"] = now

                out.append(make_denm(cam, "CONGESTION", (cam["x"], cam["y"]), 2, "Stationary traffic", now))

        else:

            info["stopped_since"] = None

        lane = st.get("lane_id")

        if lane and info["last_lane"] and lane != info["last_lane"] and lane.rsplit("_", 1)[0] == info["last_lane"].rsplit("_", 1)[0]:

            if now - info["last_denm"] >= 5:

                info["last_denm"] = now

                out.append(make_denm(cam, "LANE_CHANGE", (cam["x"], cam["y"]), 1, f"Lane change to {lane}", now))

        info["last_lane"] = lane

        for m in out:

            m["_attack"] = None

        return out



    def _run_scenario_schedule(self, now: float):

        for i, sched in enumerate(self.scenario.attacks):

            if i in self.scenario_launched or now < sched.at_time:

                continue

            self.scenario_launched.add(i)

            for _ in range(sched.count):

                vid = self._pick_attacker()

                if vid:

                    self.launch_attack(vid, sched.attack_type)



    # ------------------------------------------------------------ attribution

    def _attribute(self, msg: Dict, res: Dict, loc) -> Optional[str]:

        """Who is accountable for this message? Forged identities are traced via RSU localization."""

        sid = msg["sender_id"]

        if msg["type"] == "VAM":

            return None  # pedestrians are not part of the vehicle trust system

        forged = res["sig_status"] == "unknown_cert" or res["attack_type"] == "replay"

        if not forged and sid in self.vehicle_states:

            return sid

        if loc is None:

            return None

        dists = sorted((math.hypot(st["position"][0] - loc[0], st["position"][1] - loc[1]), vid)

                       for vid, st in self.vehicle_states.items())

        if not dists or dists[0][0] > 10.0:

            return None

        # only attribute when the localization is unambiguous; otherwise the message is

        # still flagged but nobody is penalized (avoids accusing a queued neighbour)

        if len(dists) > 1 and dists[1][0] - dists[0][0] < 4.0:

            return None

        return dists[0][1]



    # ------------------------------------------------------------- records

    def _make_record(self, msg: Dict, res: Dict, accused: Optional[str], now: float) -> Dict:

        sid = msg["sender_id"]

        record = {

            "msg_id": msg["msg_id"], "time": now, "timestamp": msg["timestamp"], "sender": sid,

            "accused": accused, "type": msg["type"], "content": summarize(msg), "event": msg.get("event"),

            "claimed_type": msg.get("claimed_type"), "emergency": bool(msg.get("emergency_flag")) or msg["type"] == "DENM" and (msg.get("event") or {}).get("event_type") == "EMERGENCY_VEHICLE_APPROACH",

            "sender_pos": (msg["x"], msg["y"]), "speed": msg["speed"], "heading": msg["heading"],

            "sender_trust": round(self.trust.score(accused or sid), 4),

            "classification": res["classification"], "attack_type": res["attack_type"],

            "probability": res["probability"], "ai_confidence": res["confidence"],

            "sig_status": res["sig_status"], "rule_hits": res["rule_hits"], "tx_id": None,

            "pseudonym": msg.get("pseudonym"), "delivered_to": 0,

        }

        return record



    def _deliver(self, record: Dict, msg: Dict, res: Dict, accused: Optional[str], deliveries, now: float):

        sid = msg["sender_id"]

        verdict = res["classification"]

        truth = self._truth(msg, res)

        responsible = accused or sid

        # would a receiver act on this message? (valid certificate, not flagged, trusted sender)

        accepted = (verdict == "Normal" and res["sig_status"] == "valid"

                    and (msg["type"] == "VAM" or self.trust.status(responsible) == "trusted"))

        colluders = set(self.attacks.colluders(accused)) if accused else set()

        delivered = 0

        for dl in deliveries:

            if not dl.delivered:

                continue

            delivered += 1

            if dl.channel == "V2I":

                rs = self.rsu_stats[dl.receiver_id]

                rs["received"] += 1

                if verdict != "Normal":

                    rs["flagged"] += 1

                continue

            rid = dl.receiver_id

            if rid in self.ped_states:

                self.counters["v2p_to_pedestrians"] += 1

                continue

            if truth:

                self.counters["malicious_delivered"] += 1

                self.counters["malicious_accepted"] += int(accepted)

            else:

                self.counters["honest_delivered"] += 1

                self.counters["honest_rejected"] += int(not accepted)

            rpos = self.vehicle_states[rid]["position"] if rid in self.vehicle_states else (0, 0)

            self.received[rid].append((record, round(dl.distance, 1), round(dl.latency_ms, 2), (round(rpos[0], 1), round(rpos[1], 1))))

            rinfo = self.vehicles.get(rid)

            if rinfo:

                rinfo["received"] += 1

            self.edges[(sid, rid)][verdict] += 1

            if accused is not None:

                # receivers file local reports; attackers lie, local evidence is sometimes inconclusive

                if rid in colluders:

                    vote = "Normal"               # colluders vouch for each other

                elif self.attacks.colluders(rid):

                    vote = "Malicious"            # ... and bad-mouth honest neighbours

                elif self.attacks.is_attacker(rid):

                    vote = "Normal"

                elif verdict != "Normal" and self.rng.random() < 0.08:

                    vote = "Normal"

                else:

                    vote = verdict

                self.reports.submit(rid, accused, vote, self.trust.score(rid), now)

        record["delivered_to"] = delivered

        self.counters["transmissions"] += 1

        self.counters[f"type_{msg['type']}"] += 1

        self.msg_times.append(now)

        if verdict != "Normal":

            self.counters[f"flagged_{verdict}"] += 1

        sinfo = self.vehicles.get(sid)

        if sinfo is None and accused:

            sinfo = self.vehicles.get(accused)

        if sinfo:

            sinfo["sent"] += 1

            sinfo["last_prob"] = res["probability"]

            if verdict == "Suspicious":

                sinfo["suspicious_sent"] += 1

            elif verdict == "Malicious":

                sinfo["malicious_sent"] += 1

        self.sent[accused or sid].append(record)

        if verdict != "Normal" or record["emergency"]:

            self.db_queue["messages"].append(record)



    def _truth(self, msg: Dict, res: Dict) -> Optional[str]:

        """Ground-truth label. Messages signed with a revoked certificate are malicious by definition."""

        if msg["_attack"]:

            return msg["_attack"]

        if res["sig_status"] == "revoked":

            return "revoked_identity"

        return None



    def _account_ground_truth(self, msg: Dict, res: Dict, now: float):

        truth = self._truth(msg, res)

        predicted = res["classification"] != "Normal"

        key = ("tp" if predicted else "fn") if truth else ("fp" if predicted else "tn")

        self.confusion[key] += 1

        true_label = truth or "normal"

        pred_label = res["attack_type"] if predicted else "normal"

        self.confusion_matrix[true_label][pred_label] += 1

        if truth:

            pa = self.per_attack[truth]

            pa["total"] += 1

            if predicted:

                pa["detected"] += 1

                if res["attack_type"] == truth:

                    pa["correct_type"] += 1

            rep = self.attack_reports.get(msg["_tx"])

            if predicted and rep and rep["first_detection"] is None and rep["attack_type"] == truth:

                rep["first_detection"] = {"time": now, "latency_s": round(now - rep["launched_at"], 2),

                                          "probability": res["probability"], "attack_type": res["attack_type"]}



    # ------------------------------------------------------------- decisions

    def _handle_detection(self, vid: str, msg: Dict, res: Dict, record: Dict, now: float):

        info = self.vehicles.get(vid)

        if info is None:

            return

        info["detections"][res["attack_type"]] += 1

        if not self.trust_enabled:

            return  # "no trust management" baseline: detections are not acted upon

        cons = self.reports.consensus(vid, now)

        before = self.trust.score(vid)

        ev = self.trust.penalize(vid, now, res["probability"], cons["ratio"], res["attack_type"],

                                 res["classification"], self.contract.on_chain_reports(vid),

                                 cons["reporters"], cons["flagging"])

        if ev is None:

            return

        self._queue_trust(vid, ev)

        after = ev.new_score

        if vid in self.trust.blacklisted and now - self._last_chain_report.get(vid, -1e9) < BLACKLISTED_REPORT_INTERVAL:

            return  # already blacklisted: keep on-chain reporting of ongoing misbehaviour sparse

        self._last_chain_report[vid] = now

        rsu = self._nearest_rsu(self.vehicle_states[vid]["position"]) if vid in self.vehicle_states else self.rsus[0]["id"]



        evidence = None

        top = max(res["rule_hits"], key=lambda h: h["score"]) if res["rule_hits"] else None

        ev_key = (vid, res["attack_type"])

        # a blacklisted vehicle using its revoked certificate is already on record: no new evidence per message

        repeat_offence = vid in self.trust.blacklisted and res["attack_type"] == "revoked_identity"

        if res["probability"] > self.contract.FLAG_THRESHOLD and not repeat_offence and \

                now - self._last_evidence.get(ev_key, -1e9) >= EVIDENCE_INTERVAL:

            self._last_evidence[ev_key] = now

            evidence = self.evidence.create(

                vehicle_id=vid, pseudonym=msg.get("pseudonym"), attack_type=res["attack_type"],

                label=ATTACK_LABELS.get(res["attack_type"], res["attack_type"]), time=now,

                location=[round(c, 1) for c in self.vehicle_states.get(vid, {}).get("position", (msg["x"], msg["y"]))],

                sender=msg["sender_id"], receivers=record["delivered_to"], original_message=public_view(msg),

                expected=top["expected"] if top else "model: normal behaviour",

                observed=top["observed"] if top else f"model: {res['model_label']} ({res['model_probability']:.2f})",

                rule_hits=res["rule_hits"], ai_probability=res["probability"], model_probability=res["model_probability"],

                model_label=res["model_label"], classification=res["classification"], consensus=round(cons["ratio"], 3),

                reporters=cons["reporters"], flagging=cons["flagging"], trust_before=round(before, 4),

                trust_after=round(after, 4), registered_type=res["registered_type"],

                claimed_type=msg.get("claimed_type"), reporting_rsu=rsu, tx_id=None, block=None,

            )

        detection = dict(res, consensus=cons["ratio"], reason=ev.reason)

        outcome = self.contract.evaluate_detection(vid, detection, before, after, rsu, now, evidence)

        tx_ids = [t.tx_id for t in outcome["txs"]]

        if tx_ids:

            record["tx_id"] = tx_ids[0]

            info["blockchain_txs"].extend(tx_ids)

        if evidence:

            evidence["tx_id"] = next((t.tx_id for t in outcome["txs"] if t.tx_type.value == "EVIDENCE_RECORD"), None)

            self.db_queue["evidence"].append(evidence)

        rep = self.attack_reports.get(vid)

        if rep and self.attacks.is_attacker(vid):

            if evidence:

                rep["evidence_ids"].append(evidence["attack_id"])

            rep["tx_ids"].extend(tx_ids)



        if res["classification"] == "Malicious" or after < self.trust.trusted_threshold:

            self._detection_alert(vid, msg, res, before, after, evidence, tx_ids, cons)

        label = ATTACK_LABELS.get(res["attack_type"], res["attack_type"])

        if "notify_network" in outcome["actions"] and now - self._last_notify.get(vid, -1e9) >= NOTIFY_INTERVAL:

            self._last_notify[vid] = now

            self._rsu_notify(rsu, vid, f"{vid} flagged: {label} (trust {after * 100:.0f})", tx_ids[0] if tx_ids else None, now)

        if "blacklist" in outcome["actions"]:

            bl = self.trust.blacklist(vid, now, label)

            self._queue_trust(vid, bl)

            self.registry.revoke(vid, f"Blacklisted for {res['attack_type']}", now)

            if rep and rep.get("blacklisted_at") is None:

                rep["blacklisted_at"] = now

            self._rsu_notify(rsu, vid, f"{vid} blacklisted, certificates revoked (CRL update)", tx_ids[-1] if tx_ids else None, now)

            self._alert("critical", "blacklist", vid, f"Vehicle {vid} blacklisted",

                        f"Trust {after * 100:.1f} below {self.contract.BLACKLIST_THRESHOLD * 100:.0f}; certificate revoked",

                        {"trust": after, "tx_id": tx_ids[-1] if tx_ids else None}, force=True)



    def _detection_alert(self, vid, msg, res, before, after, evidence, tx_ids, cons):

        info = self.vehicles.get(vid, {})

        attack = res["attack_type"]

        label = ATTACK_LABELS.get(attack, attack)

        severity = "critical" if res["classification"] == "Malicious" else "warning"

        details = {

            "attack_type": attack, "probability": res["probability"], "trust_before": before, "trust_after": after,

            "status": self.trust.status(vid), "actual_type": info.get("type"), "claimed_type": msg.get("claimed_type"),

            "attack_id": evidence["attack_id"] if evidence else None, "tx_id": tx_ids[0] if tx_ids else None,

            "consensus": round(cons["ratio"], 3), "reporters": cons["reporters"], "flagging": cons["flagging"],

            "position": list(self.vehicle_states.get(vid, {}).get("position", (msg["x"], msg["y"]))),

        }

        title = "EMERGENCY VEHICLE SPOOFING" if attack == "emergency_spoofing" else label

        text = (f"{vid}: actual {info.get('type')}, claims {msg.get('claimed_type')}" if attack == "emergency_spoofing"

                else f"{vid}: {label.lower()} (p={res['probability']:.2f})")

        self._alert(severity, attack, vid, title, text, details)



    def _alert(self, severity: str, kind: str, vid: str, title: str, message: str, details: Dict, force: bool = False):

        key = (vid, kind)

        cooldown = ALERT_COOLDOWN * 6 if vid in self.trust.blacklisted else ALERT_COOLDOWN

        if not force and self.sim_time - self._last_alert.get(key, -1e9) < cooldown:

            return

        self._last_alert[key] = self.sim_time

        self._alert_seq += 1

        alert = {"id": f"AL-{self._alert_seq:05d}", "time": self.sim_time, "wall_time": time.time(),

                 "severity": severity, "kind": kind, "vehicle_id": vid, "title": title, "message": message,

                 "details": details}

        self.alerts.append(alert)

        self.events_out.append({"type": "alert", "data": alert})

        self.db_queue["alerts"].append(alert)



    def _queue_trust(self, vid: str, ev):

        row = {"vehicle_id": vid, "old_score": ev.old_score, "new_score": ev.new_score, "reason": ev.reason,

               "timestamp": ev.time, "kind": ev.kind, "attack_type": ev.attack_type}

        self.db_queue["trust"].append(row)

        if ev.kind != "reward":

            self.events_out.append({"type": "trust_change", "data": row})



    def _check_rehabilitation(self, now: float):

        for vid in list(self.trust.blacklisted):

            if vid in self.vehicle_states and self.trust.rehabilitation_due(vid, now) and not self.attacks.is_attacker(vid):

                before = self.trust.score(vid)

                ev = self.trust.rehabilitate(vid, now)

                self._queue_trust(vid, ev)

                self.registry.reinstate(vid, now)

                rsu = self._nearest_rsu(self.vehicle_states[vid]["position"]) if vid in self.vehicle_states else self.rsus[0]["id"]

                tx = self.contract.rehabilitate(vid, before, ev.new_score, rsu, now)

                if vid in self.vehicles:

                    self.vehicles[vid]["blockchain_txs"].append(tx.tx_id)

                self._alert("info", "rehabilitate", vid, f"Vehicle {vid} rehabilitated",

                            ev.reason, {"trust_after": ev.new_score, "tx_id": tx.tx_id}, force=True)



    def _seal_blocks(self, now: float):

        block = self.chain.seal(now)

        if block is None:

            return

        if block.validator in self.rsu_stats:

            self.rsu_stats[block.validator]["blocks_sealed"] += 1

        for tx in block.transactions:

            if tx.tx_type.value == "EVIDENCE_RECORD" and tx.event_id:

                rec = self.evidence.get(tx.event_id)

                if rec:

                    rec["block"] = block.index

        types = Counter(tx.tx_type.value for tx in block.transactions)

        self.events_out.append({"type": "block", "data": {

            "index": block.index, "hash": block.hash, "prev_hash": block.previous_hash, "validator": block.validator,

            "time": block.timestamp, "tx_count": len(block.transactions), "tx_types": dict(types)}})



    # ------------------------------------------------------ RSU notifications

    def _rsu_notify(self, rsu_id: str, subject: str, text: str, tx_id: Optional[str], now: float):

        """V2I downlink: the RSU warns vehicles in its coverage about a flagged / revoked vehicle."""

        rsu = next(r for r in self.rsus if r["id"] == rsu_id)

        record = {

            "msg_id": _next_id("MBR"), "time": now, "timestamp": now, "sender": rsu_id, "accused": None,

            "type": "MBR", "content": text, "event": None, "claimed_type": "rsu", "emergency": False,

            "sender_pos": (rsu["x"], rsu["y"]), "speed": 0.0, "heading": 0.0, "sender_trust": 1.0,

            "classification": "Normal", "attack_type": "normal", "probability": 0.0, "ai_confidence": 1.0,

            "sig_status": "valid", "rule_hits": [], "tx_id": tx_id, "pseudonym": None, "delivered_to": 0,

            "subject": subject,

        }

        n = 0

        for vid, st in self.vehicle_states.items():

            d = math.hypot(st["position"][0] - rsu["x"], st["position"][1] - rsu["y"])

            if d <= self.channel.rsu_range and vid != subject:

                pos = st["position"]

                self.received[vid].append((record, round(d, 1), round(self.channel._latency_ms(d), 2),

                                           (round(pos[0], 1), round(pos[1], 1))))

                n += 1

        record["delivered_to"] = n

        self.counters["i2v_notifications"] += 1

        self.counters["i2v_deliveries"] += n



    # ------------------------------------------------------------- replay

    def _write_run_meta(self, final: bool = False):

        if not (self.record_replay and self.persist_runs):

            return

        try:

            os.makedirs(RUNS_DIR, exist_ok=True)

            meta = {"run_id": self.run_id, "scenario": self.scenario.id, "scenario_name": self.scenario.name,

                    "started_at": self._run_started, "mock_mode": self.mock_mode, "sim_time": self.sim_time,

                    "frames": len(self._frames), "finished": final,

                    "attacks": sum(1 for h in self.attacks.history if h["event"] == "launch")}

            with open(os.path.join(RUNS_DIR, f"{self.run_id}.meta.json"), "w") as fh:

                json.dump(meta, fh)

        except OSError as e:  # pragma: no cover

            logger.warning("Could not write run metadata: %s", e)



    def _record_frame(self, states: Dict[str, Dict], now: float):

        frame = {

            "t": now,

            "v": [[vid, self.vehicles[vid]["type"], self.vehicles[vid]["claimed_type"], round(st["position"][0], 1),

                   round(st["position"][1], 1), round(st.get("heading", 0.0)), self.trust.status(vid),

                   round(self.trust.score(vid), 3), self.attacks.active[vid].attack_type if vid in self.attacks.active else None]

                  for vid, st in states.items()],

            "p": [[pid, round(p["position"][0], 1), round(p["position"][1], 1)] for pid, p in self.ped_states.items()],

            "a": len(self.alerts),

        }

        self._frames.append(frame)

        self._frame_buffer.append(json.dumps(frame, separators=(",", ":")))

        if len(self._frame_buffer) >= 40:

            self._flush_frames()



    def _flush_frames(self, final: bool = False):

        if not self._frame_buffer or not (self.record_replay and self.persist_runs):

            self._frame_buffer = []

            return

        try:

            os.makedirs(RUNS_DIR, exist_ok=True)

            with open(os.path.join(RUNS_DIR, f"{self.run_id}.jsonl"), "a") as fh:

                fh.write("\n".join(self._frame_buffer) + "\n")

            self._frame_buffer = []

            self._write_run_meta(final)

        except OSError as e:  # pragma: no cover

            logger.warning("Could not write replay frames: %s", e)



    def replay_frames(self, start: float = 0.0, end: float = 1e12, stride: int = 1) -> List[Dict]:

        with self.lock:

            frames = [f for f in self._frames if start <= f["t"] <= end]

        return frames[::max(1, stride)]



    # --------------------------------------------------------- performance

    @staticmethod

    def _pctl(values, q: float) -> float:

        if not values:

            return 0.0

        vals = sorted(values)

        return float(vals[min(len(vals) - 1, int(q * len(vals)))])



    def get_performance(self) -> Dict:

        with self.lock:

            lat, e2e, infer = list(self.perf["latency"]), list(self.perf["e2e"]), list(self.perf["infer"])

            txl = list(self.chain.latency_samples)

            seal = list(self.chain.seal_samples)

            ch = self.channel.stats

            sent = max(1, self.counters["transmissions"])

            msg_bytes = ch["bytes"] / max(1, ch["delivered"])

            sec_bytes = SIGNATURE_BYTES + CERTIFICATE_BYTES

            det = [r["first_detection"]["latency_s"] for r in self.attack_reports.values() if r.get("first_detection")]

            iso = [r["blacklisted_at"] - r["launched_at"] for r in self.attack_reports.values() if r.get("blacklisted_at")]

            per_attack_latency: Dict[str, List[float]] = defaultdict(list)

            for r in self.attack_reports.values():

                if r.get("first_detection"):

                    per_attack_latency[r["attack_type"]].append(r["first_detection"]["latency_s"])

            cpu = [c for _, c in self.perf["cpu"]]

            mem = _PROC.memory_info().rss / 1e6 if _PROC is not None else None

            perf_bc = self.chain.performance(self.sim_time)

            return {

                "v2x": {

                    "latency_avg_ms": sum(lat) / len(lat) if lat else 0.0,

                    "latency_p50_ms": self._pctl(lat, 0.5), "latency_p95_ms": self._pctl(lat, 0.95),

                    "e2e_avg_ms": sum(e2e) / len(e2e) if e2e else 0.0, "e2e_p95_ms": self._pctl(e2e, 0.95),

                    "pdr": self.channel.packet_delivery_ratio(),

                    "packet_loss": 1 - self.channel.packet_delivery_ratio(),

                    "throughput_kbps": (ch["bytes"] * 8 / 1000) / self.sim_time if self.sim_time else 0.0,

                    "messages_sent": self.counters["transmissions"], "deliveries": ch["delivered"], "lost": ch["lost"],

                    "avg_receivers_per_msg": ch["delivered"] / sent,

                    "avg_message_bytes": msg_bytes, "security_overhead_bytes": sec_bytes,

                    "security_overhead_ratio": sec_bytes / msg_bytes if msg_bytes else 0.0,

                    "v2v": ch["v2v"], "v2i": ch["v2i"], "v2p": ch["v2p"] + self.counters["v2p_to_pedestrians"],

                    "i2v_notifications": self.counters["i2v_notifications"],

                },

                "blockchain": {

                    **perf_bc,

                    "tx_latency_p50_s": self._pctl(txl, 0.5), "tx_latency_p95_s": self._pctl(txl, 0.95),

                    "consensus_time_ms": sum(seal) / len(seal) if seal else 0.0,

                    "consensus_time_p95_ms": self._pctl(seal, 0.95),

                    "tx_bytes": self.chain.stats["tx_bytes"],

                    "avg_tx_bytes": self.chain.stats["tx_bytes"] / max(1, self.chain.stats["tx_committed"]),

                    "comm_overhead_bytes": self.chain.stats["tx_bytes"] * len(getattr(self.chain, "validators", [1])),

                },

                "ai": {

                    "model": self.detector.model_name, "mode": self.detector.mode,

                    "inference_avg_ms": sum(infer) / len(infer) if infer else 0.0,

                    "inference_p95_ms": self._pctl(infer, 0.95),

                    "detection_latency_avg_s": sum(det) / len(det) if det else None,

                    "detection_latency_max_s": max(det) if det else None,

                    "isolation_time_avg_s": sum(iso) / len(iso) if iso else None,

                    "per_attack_detection_latency_s": {k: sum(v) / len(v) for k, v in per_attack_latency.items()},

                },

                "system": {

                    "cpu_percent": cpu[-1] if cpu else None, "cpu_avg_percent": sum(cpu) / len(cpu) if cpu else None,

                    "memory_mb": mem, "step_avg_ms": sum(self.perf["step_ms"]) / len(self.perf["step_ms"]) if self.perf["step_ms"] else 0.0,

                    "step_p95_ms": self._pctl(list(self.perf["step_ms"]), 0.95),

                    "real_time_factor": (self.config.simulation.step_length * 1000 * self.speed) /

                                        max(1e-6, sum(self.perf["step_ms"]) / max(1, len(self.perf["step_ms"])) * self.speed),

                    "gpu": "not used (tree models run on CPU)",

                },

                "security_impact": {

                    "malicious_delivered": self.counters["malicious_delivered"],

                    "malicious_accepted": self.counters["malicious_accepted"],

                    "malicious_acceptance_rate": self.counters["malicious_accepted"] / max(1, self.counters["malicious_delivered"]),

                    "honest_delivered": self.counters["honest_delivered"],

                    "honest_rejected": self.counters["honest_rejected"],

                    "honest_rejection_rate": self.counters["honest_rejected"] / max(1, self.counters["honest_delivered"]),

                },

            }



    # ================================================================ snapshot

    def drain_events(self) -> List[Dict]:

        with self.lock:

            ev, self.events_out = self.events_out, []

            return ev



    def drain_db_queue(self) -> Dict[str, List[Dict]]:

        with self.lock:

            q = self.db_queue

            self.db_queue = {"trust": [], "evidence": [], "alerts": [], "messages": []}

            return q



    def _vehicle_view(self, vid: str, st: Optional[Dict]) -> Dict:

        info = self.vehicles[vid]

        trust = self.trust.score(vid)

        cons = self.reports.consensus(vid, self.sim_time)

        pos = st["position"] if st else (0.0, 0.0)

        return {

            "id": vid, "hash": vehicle_hash(vid), "type": info["type"], "claimed_type": info["claimed_type"],

            "emergency_flag": info["emergency_flag"],

            "x": round(pos[0], 2), "y": round(pos[1], 2),

            "speed": round(st.get("speed", 0.0), 2) if st else 0.0,

            "acceleration": round(st.get("acceleration", 0.0), 2) if st else 0.0,

            "heading": round(st.get("heading", 0.0), 1) if st else 0.0,

            "lane": st.get("lane_id", "") if st else "", "road": st.get("road_id", "") if st else "",

            "trust_score": round(trust, 4), "status": self.trust.status(vid),

            "reputation": round(1.0 - cons["ratio"], 4) if cons["reporters"] else round(trust, 4),

            "ai_score": round(info["last_prob"], 4),

            "message_count": info["sent"], "messages_received": info["received"],

            "suspicious_count": info["suspicious_sent"], "misbehavior_count": info["malicious_sent"],

            "detected_attacks": sum(info["detections"].values()),

            "attack_types": dict(info["detections"]),

            "blockchain_records": len(info["blockchain_txs"]),

            "gt_attack": self.attacks.active[vid].attack_type if vid in self.attacks.active else None,

            "behavior_type": "malicious" if vid in self.attacks.active else "normal",  # legacy field (experiments)

            "active": info["active"],

        }



    def get_state_snapshot(self, refresh: bool = False) -> Dict[str, Any]:

        with self.lock:

            if not refresh and self._last_snapshot is not None:

                snap = dict(self._last_snapshot)

                snap.update(simulation_running=self.is_running, paused=self.paused, speed=self.speed)

                return snap

            vehicles = [self._vehicle_view(vid, st) for vid, st in self.vehicle_states.items()]

            status_counts = Counter(v["status"] for v in vehicles)

            while self.msg_times and self.sim_time - self.msg_times[0] > 1.0:

                self.msg_times.popleft()

            stats = self.get_stats(vehicles, status_counts)

            snap = {

                "simulation_running": self.is_running, "paused": self.paused, "speed": self.speed,

                "sim_time": self.sim_time, "scenario": {"id": self.scenario.id, "name": self.scenario.name},

                "mock_mode": self.mock_mode,

                "vehicle_count": len(vehicles),

                "trusted": status_counts["trusted"], "suspicious": status_counts["suspicious"],

                "misbehaving": status_counts["malicious"] + status_counts["blacklisted"],

                "messages_total": self.counters["transmissions"],

                "blockchain_blocks": len(self.chain.chain), "blockchain_txs": self.chain.stats["tx_committed"],

                "vehicles": vehicles,

                "rsus": [{**r, "status": "online", "type": "rsu", "reputation": 1.0, **self.rsu_stats[r["id"]]} for r in self.rsus],

                "active_attacks": self.attacks.list_active(),

                "pedestrians": [{"id": pid, "x": round(p["position"][0], 1), "y": round(p["position"][1], 1),

                                 "heading": round(p["heading"])} for pid, p in self.ped_states.items()],

                "metrics": {

                    "detectionRate": stats["security"]["detection_rate"] * 100,

                    "avgTrust": stats["vehicles"]["avg_trust"],

                    "blockchainTps": stats["blockchain"]["tps"],

                    "messagesPerSec": stats["communication"]["messages_per_sec"],

                },

                "stats": stats,

            }

            if self.sim_time - self._last_timeline_t >= 1.0:

                self._last_timeline_t = self.sim_time

                self.timeline.append({"t": self.sim_time, "trusted": snap["trusted"], "suspicious": snap["suspicious"],

                                      "malicious": snap["misbehaving"], "msgs_per_sec": stats["communication"]["messages_per_sec"],

                                      "avg_trust": stats["vehicles"]["avg_trust"], "alerts": len(self.alerts),

                                      "pdr": stats["communication"]["pdr"], "latency_ms": stats["communication"]["avg_latency_ms"],

                                      "tps": stats["blockchain"]["tps"], "tx_latency_s": stats["blockchain"]["avg_tx_latency_s"],

                                      "infer_ms": (sum(list(self.perf["infer"])[-50:]) / max(1, len(list(self.perf["infer"])[-50:]))),

                                      "cpu": self.perf["cpu"][-1][1] if self.perf["cpu"] else None,

                                      "blocks": len(self.chain.chain), "detection_rate": stats["security"]["detection_rate"]})

            self._last_snapshot = snap

            return snap



    def get_stats(self, vehicles: Optional[List[Dict]] = None, status_counts: Optional[Counter] = None) -> Dict:

        with self.lock:

            if vehicles is None:

                vehicles = [self._vehicle_view(vid, st) for vid, st in self.vehicle_states.items()]

                status_counts = Counter(v["status"] for v in vehicles)

            c = self.confusion

            tp, fp, fn, tn = c["tp"], c["fp"], c["fn"], c["tn"]

            ch = self.channel.stats

            type_counts = Counter(v["type"] for v in vehicles)

            return {

                "vehicles": {

                    "total_registered": self.counters["vehicles_registered"], "active": len(vehicles),

                    "trusted": status_counts["trusted"], "suspicious": status_counts["suspicious"],

                    "malicious": status_counts["malicious"], "blacklisted": status_counts["blacklisted"],

                    "emergency": sum(type_counts[t] for t in EMERGENCY_TYPES), "by_type": dict(type_counts),

                    "avg_trust": (sum(v["trust_score"] for v in vehicles) / len(vehicles)) if vehicles else 0.0,

                },

                "communication": {

                    "messages_sent": self.counters["transmissions"], "cam": self.counters["type_CAM"],

                    "denm": self.counters["type_DENM"], "messages_received": ch["delivered"],

                    "messages_per_sec": len(self.msg_times), "v2v": ch["v2v"], "v2i": ch["v2i"],

                    "v2n": self.chain.stats["tx_committed"], "v2p": ch["v2p"] + self.counters["v2p_to_pedestrians"],

                    "vam": self.counters["type_VAM"], "i2v_notifications": self.counters["i2v_notifications"],

                    "pedestrians": len(self.ped_states), "failed": ch["lost"],

                    "pdr": self.channel.packet_delivery_ratio(), "avg_latency_ms": self.channel.avg_latency_ms(),

                    "throughput_kbps": (ch["bytes"] * 8 / 1000) / self.sim_time if self.sim_time else 0.0,

                    "overhead_bytes": ch["bytes"],

                },

                "security": {

                    "alerts": len(self.alerts), "active_attacks": len(self.attacks.active),

                    "attacks_launched": sum(1 for h in self.attacks.history if h["event"] == "launch"),

                    "evidence_records": len(self.evidence.records), "blacklisted": len(self.trust.blacklisted),

                    "flagged_suspicious": self.counters["flagged_Suspicious"], "flagged_malicious": self.counters["flagged_Malicious"],

                    "true_positives": tp, "false_positives": fp, "false_negatives": fn, "true_negatives": tn,

                    "detection_rate": tp / (tp + fn) if tp + fn else 1.0,

                    "precision": tp / (tp + fp) if tp + fp else 1.0,

                    "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,

                    "accuracy": (tp + tn) / max(1, tp + tn + fp + fn),

                    "attack_distribution": {k: dict(v) for k, v in self.per_attack.items()},

                },

                "blockchain": self.chain.performance(self.sim_time),

                "ai": self.detector.info(),

            }



    # ============================================================== queries

    def vehicle_detail(self, vid: str) -> Optional[Dict]:

        with self.lock:

            if vid not in self.vehicles:

                return None

            view = self._vehicle_view(vid, self.vehicle_states.get(vid))

            info = self.vehicles[vid]

            cert = self.registry.get(vid)

            cons = self.reports.consensus(vid, self.sim_time)

            view.update({

                "route": info.get("route", []), "first_seen": info["first_seen"], "last_seen": info["last_seen"],

                "certificate": cert.public_view() if cert else None,

                "trust_components": self.trust.components.get(vid, {}),

                "trust_weights": self.trust.weights(),

                "consensus": cons, "offences": self.trust.offences.get(vid, 0),

                "on_chain_reports": self.contract.on_chain_reports(vid),

                "evidence_ids": [e["attack_id"] for e in self.evidence.for_vehicle(vid)],

                "attack_report": self.attack_reports.get(vid),

            })

            return view



    def received_messages(self, vid: str, flt: str = "all", sender: Optional[str] = None, mtype: Optional[str] = None,

                          t_from: Optional[float] = None, t_to: Optional[float] = None, limit: int = 200,

                          privacy: bool = False) -> Dict:

        with self.lock:

            buf = list(self.received.get(vid, ()))

        out = []

        for record, dist, lat, rpos in reversed(buf):

            if not _match(record, flt, sender, mtype, t_from, t_to):

                continue

            item = {**_record_public(record), "receiver": vid, "distance": dist, "latency_ms": lat, "receiver_pos": rpos}

            out.append(self.mask(item) if privacy else item)

            if len(out) >= limit:

                break

        senders = sorted({r[0]["sender"] for r in buf})

        return {"vehicle_id": vid, "total_buffered": len(buf), "senders": senders, "messages": out, "privacy": privacy}



    def sent_messages(self, vid: str, flt: str = "all", mtype: Optional[str] = None, limit: int = 200,

                      privacy: bool = False) -> List[Dict]:

        with self.lock:

            buf = list(self.sent.get(vid, ()))

        out = [_record_public(r) for r in reversed(buf) if _match(r, flt, None, mtype, None, None)][:limit]

        return [self.mask(m) for m in out] if privacy else out



    # ----------------------------------------------------------- privacy

    def _pseudo(self, vid: Optional[str]) -> Optional[str]:

        if vid is None or vid.startswith("RSU"):

            return vid

        return self.registry.pseudonym_of(vid) or "anonymous"



    def mask(self, item: Dict) -> Dict:

        """Privacy view: real ids -> current pseudonyms, positions coarsened to a 50 m grid."""

        out = dict(item)

        for k in ("sender", "accused", "receiver", "vehicle_id", "subject"):

            if k in out:

                out[k] = self._pseudo(out[k])

        for k in ("sender_pos", "receiver_pos", "location"):

            if out.get(k):

                out[k] = [round(c / 50) * 50 for c in out[k]]

        if "original_message" in out and out["original_message"]:

            om = dict(out["original_message"])

            om["sender_id"] = self._pseudo(om.get("sender_id"))

            om["x"], om["y"] = round(om["x"] / 50) * 50, round(om["y"] / 50) * 50

            out["original_message"] = om

        subject = item.get("subject")

        if subject and out.get("content"):

            out["content"] = out["content"].replace(subject, self._pseudo(subject) or "anonymous")

        out["privacy_masked"] = True

        return out



    def comm_graph(self, min_messages: int = 1) -> Dict:

        with self.lock:

            active = set(self.vehicle_states)

            nodes = [{"id": vid, "type": self.vehicles[vid]["type"], "trust": round(self.trust.score(vid), 3),

                      "status": self.trust.status(vid), "attacker": vid in self.attacks.active}

                     for vid in active]

            ghost_nodes = set()

            edges = []

            for (s, r), cnt in self.edges.items():

                if r not in active:

                    continue

                total = sum(cnt.values())

                if total < min_messages:

                    continue

                if s not in active:

                    if s in self.vehicles:

                        continue

                    ghost_nodes.add(s)

                edges.append({"source": s, "target": r, "messages": total, "valid": cnt["Normal"],

                              "suspicious": cnt["Suspicious"], "malicious": cnt["Malicious"]})

            nodes += [{"id": g, "type": "unknown", "trust": 0.0, "status": "forged", "attacker": True} for g in ghost_nodes]

            return {"nodes": nodes, "edges": edges}



    def reset_graph(self):

        with self.lock:

            self.edges.clear()





def _record_public(record: Dict) -> Dict:

    return {k: v for k, v in record.items() if k != "rule_hits"} | {

        "status": {"Normal": "valid", "Suspicious": "suspicious", "Malicious": "malicious"}[record["classification"]],

        "reasons": [h["rule"] for h in record["rule_hits"]],

    }





def _match(record: Dict, flt: str, sender, mtype, t_from, t_to) -> bool:

    if flt == "valid" and record["classification"] != "Normal":

        return False

    if flt == "suspicious" and record["classification"] != "Suspicious":

        return False

    if flt == "malicious" and record["classification"] != "Malicious":

        return False

    if flt == "emergency" and not record["emergency"]:

        return False

    if sender and record["sender"] != sender:

        return False

    if mtype and record["type"] != mtype:

        return False

    if t_from is not None and record["time"] < t_from:

        return False

    if t_to is not None and record["time"] > t_to:

        return False

    return True
