"""

Live misbehavior detection engine.



Combines receiver-observable feature extraction, deterministic rule detectors

(ai.rule_detectors) and a trained multi-class tree model (RandomForest or

XGBoost, see ai.train_detector) into one verdict per received message:



    classification   Normal | Suspicious | Malicious

    attack_type      most likely attack family (or "normal")

    probability      misbehavior probability in [0, 1]

    confidence       confidence of the chosen label

    rule_hits        explanations with expected vs observed values

"""



import json

import logging

import math

import os

import time

from collections import defaultdict, deque

from typing import Deque, Dict, List, Optional, Tuple



import numpy as np



from ai.rule_detectors import evaluate_rules



logger = logging.getLogger(__name__)



EMERGENCY_TYPES = {"ambulance", "firetruck", "police"}



FEATURE_NAMES = [

    "bad_signature", "unknown_cert", "revoked", "type_mismatch", "claimed_emergency",

    "registered_emergency", "is_denm", "event_emergency", "dt", "moved", "position_jump",

    "implied_speed", "claimed_speed", "speed_mismatch", "claimed_accel", "implied_accel",

    "accel_abs", "accel_mismatch", "heading_motion_diff", "heading_change_rate",

    "has_localization", "loc_error", "loc_error_growth", "msg_rate", "msg_interval", "duplicate_nonce", "msg_age",

    "denm_support", "denm_near_count", "denm_contradict", "denm_distance", "event_drift", "event_reporters", "sender_in_event_group",

    "colocated_ids",

]



# attack labels the model cannot reliably tell apart from a single message; the

# (temporal, per-sender) rule label wins when both point to the same family

ATTACK_FAMILIES = [{"false_position", "gps_spoofing", "collusion"}, {"fake_accident", "collusion"}]





def _same_family(a: str, b: str) -> bool:

    return any(a in fam and b in fam for fam in ATTACK_FAMILIES)



MALICIOUS_THRESHOLD = 0.8

SUSPICIOUS_THRESHOLD = 0.5





def _angdiff(a: float, b: float) -> float:

    d = abs(a - b) % 360

    return 360 - d if d > 180 else d





def classify(prob: float) -> str:

    if prob >= MALICIOUS_THRESHOLD:

        return "Malicious"

    if prob >= SUSPICIOUS_THRESHOLD:

        return "Suspicious"

    return "Normal"





class MisbehaviorDetector:

    MODES = ("hybrid", "rules", "model", "none")



    def __init__(self, registry, model_dir: Optional[str] = None, mode: str = "hybrid"):

        self.registry = registry

        self.mode = mode  # hybrid = rules + model; used by the experiment baselines

        self.model = None

        self.model_classes: List[str] = []

        self.model_name = "rules-only"

        self.feature_importances: Dict[str, float] = {}

        self.reset()

        if model_dir:

            self.load_model(model_dir)



    # ------------------------------------------------------------------ state

    def reset(self):

        self.hist: Dict[str, Dict] = {}

        self.nonces: Dict[str, float] = {}

        self.rates: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=64))

        self.latest_cam: Dict[str, Tuple[float, float, float, float]] = {}

        self.last_event: Dict[str, Tuple[str, float, float, float]] = {}

        self.event_reports: Deque[Tuple[float, str, str, float, float]] = deque(maxlen=2000)

        self.contested_group: Dict[str, float] = {}   # sender -> last time it co-reported a contested event

        self.recent_loc: Deque[Tuple[float, str, float, float]] = deque(maxlen=2000)

        self.stats = {"inferences": 0, "total_ms": 0.0, "batches": 0}



    def load_model(self, model_dir: str) -> bool:

        path = os.path.join(model_dir, "mbd_model.joblib")

        if not os.path.exists(path):

            logger.warning("No trained detector at %s - running rules only", path)

            return False

        try:

            import joblib

            bundle = joblib.load(path)

            if bundle.get("features") != FEATURE_NAMES:

                logger.warning("Detector model feature set mismatch - retrain with `python -m ai.train_detector`")

                return False

            self.model = bundle["model"]

            self.model_classes = list(bundle["classes"])

            self.model_name = bundle.get("name", "model")

            self.feature_importances = bundle.get("feature_importances", {})

            logger.info("Loaded detector model %s (%d classes)", self.model_name, len(self.model_classes))

            return True

        except Exception as e:  # pragma: no cover - defensive

            logger.error("Failed to load detector model: %s", e)

            return False



    # -------------------------------------------------------------- features

    def extract(self, msg: Dict, localized: Optional[Tuple[float, float]], now: float) -> Tuple[Dict[str, float], Dict]:

        sid = msg["sender_id"]

        status = self.registry.verify(msg)

        cert = self.registry.by_cert(msg.get("cert_id", ""))

        registered_type = cert.registered_type if cert else "unknown"

        claimed = msg.get("claimed_type", "car")

        ev = msg.get("event") or {}

        is_denm = msg["type"] == "DENM"

        event_type = ev.get("event_type")



        f = dict.fromkeys(FEATURE_NAMES, 0.0)

        f["bad_signature"] = float(status == "bad_signature")

        f["unknown_cert"] = float(status == "unknown_cert")

        f["revoked"] = float(status == "revoked")

        f["type_mismatch"] = float(cert is not None and claimed != registered_type)

        f["claimed_emergency"] = float(bool(msg.get("emergency_flag")) or claimed in EMERGENCY_TYPES)

        f["registered_emergency"] = float(registered_type in EMERGENCY_TYPES)

        f["is_denm"] = float(is_denm)

        f["event_emergency"] = float(event_type == "EMERGENCY_VEHICLE_APPROACH")

        f["claimed_speed"] = msg["speed"]

        f["claimed_accel"] = msg["accel"]

        f["accel_abs"] = abs(msg["accel"])

        f["msg_age"] = max(0.0, now - msg["timestamp"])



        nonce_seen = msg["nonce"] in self.nonces

        f["duplicate_nonce"] = float(nonce_seen)



        # message rate from this claimed identity over the last second

        times = self.rates[sid]

        f["msg_rate"] = float(sum(1 for t in times if now - t <= 1.0) + 1)

        f["msg_interval"] = now - times[-1] if times else 1.0



        h = self.hist.get(sid)

        if h and not nonce_seen and not is_denm:

            dt = max(1e-3, msg["timestamp"] - h["t"])

            dx, dy = msg["x"] - h["x"], msg["y"] - h["y"]

            moved = math.hypot(dx, dy)

            rad = math.radians(h["heading"])

            pred = (h["x"] + h["speed"] * dt * math.sin(rad), h["y"] + h["speed"] * dt * math.cos(rad))

            f["dt"] = dt

            f["moved"] = moved

            f["position_jump"] = math.hypot(msg["x"] - pred[0], msg["y"] - pred[1])

            f["implied_speed"] = moved / dt

            # compare distance travelled with the mean of previous and current claimed speed (tolerates hard braking)

            f["speed_mismatch"] = abs((msg["speed"] + h["speed"]) / 2 - moved / dt) if dt >= 0.5 else 0.0

            f["implied_accel"] = (msg["speed"] - h["speed"]) / dt

            f["accel_mismatch"] = abs(msg["accel"] - f["implied_accel"])

            if moved > 5:

                motion_dir = math.degrees(math.atan2(dx, dy)) % 360  # SUMO: 0 = north, clockwise

                f["heading_motion_diff"] = _angdiff(msg["heading"], motion_dir)

            f["heading_change_rate"] = _angdiff(msg["heading"], h["heading"]) / dt



        if localized is not None:

            f["has_localization"] = 1.0

            f["loc_error"] = math.hypot(msg["x"] - localized[0], msg["y"] - localized[1])

            if h and h.get("loc_error") is not None and not nonce_seen and not is_denm:

                f["loc_error_growth"] = (f["loc_error"] - h["loc_error"]) / max(0.5, msg["timestamp"] - h["t"])

            lx, ly = localized

            ids = {s for (t, s, x, y) in self.recent_loc

                   if now - t <= 1.0 and s != sid and abs(x - lx) < 5 and abs(y - ly) < 5}

            f["colocated_ids"] = float(len(ids))



        if is_denm and ev:

            ex, ey = ev["x"], ev["y"]

            # other stations that reported the same kind of event nearby (possible collusion group)

            reporters = {s for (t, s, et, x, y) in self.event_reports

                         if now - t <= 10 and et == event_type and math.hypot(x - ex, y - ey) <= 40}

            reporters.add(sid)

            f["event_reporters"] = float(len(reporters))

            if event_type not in ("EMERGENCY_VEHICLE_APPROACH", "LANE_CHANGE"):

                self.event_reports.append((now, sid, event_type, ex, ey))

            # corroboration only counts *independent* vehicles (not the reporters themselves)

            near = [(s, sp) for s, (x, y, sp, t) in self.latest_cam.items()

                    if s not in reporters and now - t <= 2.0 and math.hypot(x - ex, y - ey) <= 80]

            f["denm_near_count"] = float(len(near))

            f["denm_support"] = (sum(1 for _, sp in near if sp < 3.0) / len(near)) if near else 0.0

            f["denm_contradict"] = float(sum(1 for _, sp in near if sp > 6.0))

            f["denm_distance"] = math.hypot(msg["x"] - ex, msg["y"] - ey)

            prev = self.last_event.get(sid)

            if prev and prev[0] == event_type and now - prev[3] <= 10 and event_type not in ("EMERGENCY_VEHICLE_APPROACH", "LANE_CHANGE"):

                f["event_drift"] = math.hypot(ex - prev[1], ey - prev[2])

            self.last_event[sid] = (event_type, ex, ey, now)



        if is_denm and f["event_reporters"] >= 2 and event_type in ("ACCIDENT", "ROAD_HAZARD") \

                and f["denm_contradict"] >= 1 and f["denm_support"] < 0.2:

            for (t, s2, et, x, y) in self.event_reports:

                if now - t <= 10 and et == event_type and math.hypot(x - ev["x"], y - ev["y"]) <= 40:

                    self.contested_group[s2] = now

        f["sender_in_event_group"] = float(now - self.contested_group.get(sid, -1e9) <= 10)



        # did this sender just report an accident/hazard at the place where it claims to be?

        le = self.last_event.get(sid)

        at_own_event = bool(le and le[0] in ("ACCIDENT", "ROAD_HAZARD") and now - le[3] <= 10

                            and math.hypot(msg["x"] - le[1], msg["y"] - le[2]) <= 30)



        # sticky per-sender context for rule labelling

        state = self.hist.get(sid, {})

        ctx = {

            "registered_type": registered_type,

            "claimed_type": claimed,

            "event_type": event_type,

            "position_label": state.get("position_label"),

            "heading_violations": (state.get("heading_violations", 0) + 1) if f["heading_motion_diff"] > 75 and f["moved"] > 5 else 0,

            "sig_status": status,

            "at_own_event": at_own_event,

        }

        anchor = state.get("loc_anchor")

        if f["has_localization"] and f["loc_error"] > 25:

            if anchor is None:

                ctx["loc_anchor"] = (f["loc_error"], now)

            else:

                ctx["loc_anchor"] = anchor

                span = now - anchor[1]

                if span >= 4.0:

                    # sustained drift of the position error => GPS spoofing, stable offset => false position

                    drift_rate = (f["loc_error"] - anchor[0]) / span

                    ctx["position_label"] = "gps_spoofing" if drift_rate > 2.0 else "false_position"

            if not ctx.get("position_label"):

                ctx["position_label"] = "false_position" if f["loc_error"] > 60 else "gps_spoofing"

        return f, ctx



    def _update_state(self, msg: Dict, f: Dict[str, float], ctx: Dict, localized, now: float):

        sid = msg["sender_id"]

        self.nonces[msg["nonce"]] = now

        self.rates[sid].append(now)

        if localized is not None:

            self.recent_loc.append((now, sid, localized[0], localized[1]))

        if f["duplicate_nonce"] or msg["type"] == "DENM":

            return

        prev = self.hist.get(sid, {})

        self.hist[sid] = {

            "x": msg["x"], "y": msg["y"], "t": msg["timestamp"], "speed": msg["speed"],

            "heading": msg["heading"],

            "loc_error": f["loc_error"] if f["has_localization"] else None,

            "position_label": ctx.get("position_label") if f["loc_error"] > 25 else prev.get("position_label") if f["loc_error"] > 15 else None,

            "loc_anchor": ctx.get("loc_anchor") if f["loc_error"] > 25 else prev.get("loc_anchor") if f["loc_error"] > 15 else None,

            "heading_violations": ctx["heading_violations"] if f["heading_motion_diff"] > 75 and f["moved"] > 5 else 0,

        }

        self.latest_cam[sid] = (msg["x"], msg["y"], msg["speed"], now)



    def prune(self, now: float, active_senders=None):

        if len(self.nonces) > 20000:

            self.nonces = {n: t for n, t in self.nonces.items() if now - t < 30}

        for sid in [s for s, (_, _, _, t) in self.latest_cam.items() if now - t > 10]:

            self.latest_cam.pop(sid, None)

            self.hist.pop(sid, None)

            self.rates.pop(sid, None)

            self.last_event.pop(sid, None)

            self.contested_group.pop(sid, None)

        while self.event_reports and now - self.event_reports[0][0] > 15:

            self.event_reports.popleft()



    # -------------------------------------------------------------- inference

    def detect_batch(self, items: List[Tuple[Dict, Optional[Tuple[float, float]]]], now: float) -> List[Dict]:

        if not items:

            return []

        t0 = time.perf_counter()

        while self.recent_loc and now - self.recent_loc[0][0] > 1.0:

            self.recent_loc.popleft()

        extracted = []

        for msg, loc in items:

            f, ctx = self.extract(msg, loc, now)

            self._update_state(msg, f, ctx, loc, now)

            extracted.append((f, ctx))



        model_probs = None

        if self.model is not None and self.mode in ("hybrid", "model"):

            X = np.array([[f[n] for n in FEATURE_NAMES] for f, _ in extracted], dtype=float)

            try:

                model_probs = self.model.predict_proba(X)

            except Exception as e:  # pragma: no cover

                logger.error("Model inference failed: %s", e)



        results = []

        for i, (f, ctx) in enumerate(extracted):

            hits = evaluate_rules(f, ctx) if self.mode in ("hybrid", "rules") else []

            top_rule = max(hits, key=lambda h: h.score) if hits else None

            rule_prob = top_rule.score if top_rule else 0.0

            specific = [h for h in hits if h.attack_type != "revoked_identity" and h.score >= SUSPICIOUS_THRESHOLD]

            if top_rule and top_rule.attack_type == "revoked_identity" and specific:

                top_rule = max(specific, key=lambda h: h.score)  # keep the max probability, report the specific attack



            model_prob, model_label, model_conf = 0.0, "normal", 0.0

            if model_probs is not None:

                row = model_probs[i]

                idx = int(np.argmax(row))

                model_label = self.model_classes[idx]

                model_conf = float(row[idx])

                if "normal" in self.model_classes:

                    model_prob = 1.0 - float(row[self.model_classes.index("normal")])



            # a very confident "normal" model verdict vetoes weak plausibility hits (strong identity /

            # crypto rules with score >= 0.8 are authoritative)

            if top_rule and model_probs is not None and model_prob < 0.05 and rule_prob < 0.8:

                rule_prob *= 0.6

            if top_rule and rule_prob >= model_prob:

                prob, attack, conf = rule_prob, top_rule.attack_type, max(rule_prob, model_conf if model_label == top_rule.attack_type else 0.0)

            elif model_prob > 0 and model_label != "normal":

                prob, attack, conf = model_prob, model_label, model_conf

            else:

                prob = max(rule_prob, model_prob)

                attack = "normal"

                conf = model_conf if model_probs is not None else 1.0 - prob

            if top_rule and model_label != top_rule.attack_type and _same_family(model_label, top_rule.attack_type):

                attack = top_rule.attack_type

                model_label = top_rule.attack_type

            # rules and model agreeing strengthens the verdict

            if top_rule and model_label == top_rule.attack_type:

                prob = min(0.995, 1 - (1 - rule_prob) * (1 - model_prob))



            if self.mode == "none":

                prob = 0.0

            cls = classify(prob)

            if cls == "Normal":

                attack = "normal"

            results.append({

                "classification": cls,

                "attack_type": attack,

                "probability": round(prob, 4),

                "confidence": round(max(conf, prob if cls != "Normal" else 1 - prob), 4),

                "rule_hits": [h.to_dict() for h in hits],

                "model_label": model_label,

                "model_probability": round(model_prob, 4),

                "sig_status": ctx["sig_status"],

                "registered_type": ctx["registered_type"],

                "features": {k: round(v, 3) for k, v in f.items()},

            })



        elapsed = (time.perf_counter() - t0) * 1000

        self.stats["inferences"] += len(items)

        self.stats["batches"] += 1

        self.stats["total_ms"] += elapsed

        return results



    def info(self) -> Dict:

        return {

            "model": self.model_name,

            "mode": self.mode,

            "classes": self.model_classes,

            "features": FEATURE_NAMES,

            "inferences": self.stats["inferences"],

            "avg_inference_ms": self.stats["total_ms"] / max(1, self.stats["inferences"]),

            "avg_batch_ms": self.stats["total_ms"] / max(1, self.stats["batches"]),

            "thresholds": {"malicious": MALICIOUS_THRESHOLD, "suspicious": SUSPICIOUS_THRESHOLD},

        }





def load_metrics(model_dir: str) -> Optional[Dict]:

    path = os.path.join(model_dir, "metrics.json")

    if os.path.exists(path):

        with open(path) as fh:

            return json.load(fh)

    return None
