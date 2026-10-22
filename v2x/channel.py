"""

Range-based V2X radio channel.



Delivers a broadcast message to every vehicle (V2V) and RSU (V2I) within

communication range, with distance-dependent packet loss and latency.

RSUs additionally localize the physical transmitter (as an RSSI/AoA stand-in),

which detectors use to check claimed positions and attribute forged identities.

"""



import math

import random

from dataclasses import dataclass

from typing import Dict, List, Optional, Tuple



import numpy as np





@dataclass

class Delivery:

    receiver_id: str

    channel: str          # "V2V", "V2I" or "V2P"

    distance: float

    latency_ms: float

    delivered: bool





class V2XChannel:

    def __init__(self, v2v_range: float = 300.0, rsu_range: float = 500.0,

                 base_loss: float = 0.01, localization_std: float = 2.5, seed: Optional[int] = None,

                 v2p_range: float = 80.0):

        self.v2v_range = v2v_range

        self.v2p_range = v2p_range

        self.rsu_range = rsu_range

        self.base_loss = base_loss

        self.localization_std = localization_std

        self.rng = random.Random(seed)

        self._ids: List[str] = []

        self._pos = np.zeros((0, 2))

        self._rsu_ids: List[str] = []

        self._rsu_pos = np.zeros((0, 2))

        self._ped_ids: List[str] = []

        self._ped_pos = np.zeros((0, 2))

        self.load = 0  # transmissions in the current step (channel congestion)



        self.stats = {"sent": 0, "delivered": 0, "lost": 0, "v2v": 0, "v2i": 0, "v2p": 0,

                      "latency_sum_ms": 0.0, "bytes": 0}

        self.latency_samples: List[float] = []



    def update_topology(self, vehicle_positions: Dict[str, Tuple[float, float]], rsus: List[Dict],

                        pedestrian_positions: Optional[Dict[str, Tuple[float, float]]] = None):

        peds = pedestrian_positions or {}

        self._ped_ids = list(peds.keys())

        self._ped_pos = np.array([peds[p] for p in self._ped_ids], dtype=float).reshape(-1, 2)

        self._ids = list(vehicle_positions.keys())

        self._pos = np.array([vehicle_positions[v] for v in self._ids], dtype=float).reshape(-1, 2)

        self._rsu_ids = [r["id"] for r in rsus]

        self._rsu_pos = np.array([(r["x"], r["y"]) for r in rsus], dtype=float).reshape(-1, 2)

        self.load = 0



    def _loss_probability(self, distance: float, rng_max: float) -> float:

        # Log-distance style degradation near the edge of range plus congestion.

        ratio = min(1.0, distance / rng_max)

        return min(0.95, self.base_loss + 0.25 * ratio ** 4 + 0.002 * self.load)



    def _latency_ms(self, distance: float) -> float:

        propagation = distance / 3e5          # km/ms speed of light -> ms

        mac_access = self.rng.uniform(0.3, 2.5) + 0.05 * self.load

        processing = self.rng.uniform(0.2, 0.8)

        return propagation + mac_access + processing



    def broadcast(self, transmitter_id: str, tx_pos: Tuple[float, float], size_bytes: int = 300,

                  pedestrian: bool = False) -> List[Delivery]:

        """Broadcast from a vehicle (V2V + V2I + V2P) or from a pedestrian device (V2P + V2I)."""

        self.load += 1

        self.stats["sent"] += 1

        deliveries: List[Delivery] = []

        tx = np.asarray(tx_pos, dtype=float)



        if len(self._ids):

            rng_v = self.v2p_range if pedestrian else self.v2v_range

            d = np.hypot(*(self._pos - tx).T)

            for idx in np.nonzero(d <= rng_v)[0]:

                rid = self._ids[idx]

                if rid == transmitter_id:

                    continue

                dist = float(d[idx])

                ok = self.rng.random() >= self._loss_probability(dist, rng_v)

                deliveries.append(Delivery(rid, "V2P" if pedestrian else "V2V", dist, self._latency_ms(dist), ok))



        if len(self._ped_ids) and not pedestrian:

            d = np.hypot(*(self._ped_pos - tx).T)

            for idx in np.nonzero(d <= self.v2p_range)[0]:

                dist = float(d[idx])

                ok = self.rng.random() >= self._loss_probability(dist, self.v2p_range)

                deliveries.append(Delivery(self._ped_ids[idx], "V2P", dist, self._latency_ms(dist), ok))



        if len(self._rsu_ids):

            d = np.hypot(*(self._rsu_pos - tx).T)

            for idx in np.nonzero(d <= self.rsu_range)[0]:

                dist = float(d[idx])

                ok = self.rng.random() >= self._loss_probability(dist, self.rsu_range) * 0.5

                deliveries.append(Delivery(self._rsu_ids[idx], "V2I", dist, self._latency_ms(dist), ok))



        for dl in deliveries:

            if dl.delivered:

                self.stats["delivered"] += 1

                self.stats["latency_sum_ms"] += dl.latency_ms

                self.stats["bytes"] += size_bytes

                self.stats[dl.channel.lower()] += 1

                self.latency_samples.append(dl.latency_ms)

            else:

                self.stats["lost"] += 1

        return deliveries



    def localize_transmitter(self, tx_pos: Tuple[float, float]) -> Optional[Tuple[float, float]]:

        """RSU-side estimate of the physical transmitter position (None if no RSU hears it)."""

        if not len(self._rsu_ids):

            return None

        d = np.hypot(*(self._rsu_pos - np.asarray(tx_pos)).T)

        if d.min() > self.rsu_range:

            return None

        return (tx_pos[0] + self.rng.gauss(0, self.localization_std),

                tx_pos[1] + self.rng.gauss(0, self.localization_std))



    def drain_latency_samples(self) -> List[float]:

        out, self.latency_samples = self.latency_samples, []

        return out



    def packet_delivery_ratio(self) -> float:

        attempts = self.stats["delivered"] + self.stats["lost"]

        return self.stats["delivered"] / attempts if attempts else 1.0



    def avg_latency_ms(self) -> float:

        return self.stats["latency_sum_ms"] / self.stats["delivered"] if self.stats["delivered"] else 0.0



    @staticmethod

    def distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:

        return math.hypot(a[0] - b[0], a[1] - b[1])
