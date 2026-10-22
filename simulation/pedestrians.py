"""

Pedestrian (VRU) mobility for V2P communication.



Pedestrians carrying V2X-capable devices walk along the road network from

junction to junction (on a sidewalk offset from the road centre), choosing a

random next street at every junction. They send VAMs (VRU Awareness

Messages) and receive vehicle CAMs within V2P range. Movement is continuous,

so their messages are kinematically consistent.

"""



import math

import random

from typing import Dict, List, Tuple



Point = Tuple[float, float]





class PedestrianModel:

    SIDEWALK_OFFSET = (6.0, -6.0)

    WALK_SPEED = (1.0, 1.6)



    def __init__(self, geometry: Dict, count: int = 12, seed: int = 0):

        self.rng = random.Random(seed)

        nodes = [tuple(j["coord"]) for j in geometry.get("junctions", []) if j.get("type") != "internal"]

        self.nodes: List[Point] = nodes

        self.links: Dict[int, set] = {i: set() for i in range(len(nodes))}

        for edge in geometry.get("edges", []):

            shape = edge.get("shape") or []

            if len(shape) < 2 or not nodes:

                continue

            a, b = self._nearest(shape[0]), self._nearest(shape[-1])

            if a != b:

                self.links[a].add(b)

                self.links[b].add(a)

        self.peds: Dict[str, Dict] = {}

        usable = [i for i, l in self.links.items() if l]

        for i in range(count if usable else 0):

            a = self.rng.choice(usable)

            b = self.rng.choice(sorted(self.links[a]))

            self.peds[f"P{i + 1}"] = {"a": a, "b": b, "s": self.rng.uniform(0, 1),

                                      "speed": self.rng.uniform(*self.WALK_SPEED)}



    def _nearest(self, p) -> int:

        return min(range(len(self.nodes)), key=lambda i: (self.nodes[i][0] - p[0]) ** 2 + (self.nodes[i][1] - p[1]) ** 2)



    def _pose(self, ped: Dict) -> Tuple[Point, float]:

        (ax, ay), (bx, by) = self.nodes[ped["a"]], self.nodes[ped["b"]]

        x = ax + (bx - ax) * ped["s"] + self.SIDEWALK_OFFSET[0]

        y = ay + (by - ay) * ped["s"] + self.SIDEWALK_OFFSET[1]

        heading = math.degrees(math.atan2(bx - ax, by - ay)) % 360   # SUMO convention: 0 = north

        return (x, y), heading



    def step(self, dt: float):

        for ped in self.peds.values():

            (ax, ay), (bx, by) = self.nodes[ped["a"]], self.nodes[ped["b"]]

            length = max(1.0, math.hypot(bx - ax, by - ay))

            ped["s"] += ped["speed"] * dt / length

            if ped["s"] >= 1.0:

                options = sorted(self.links[ped["b"]] - {ped["a"]}) or [ped["a"]]

                ped["a"], ped["b"], ped["s"] = ped["b"], self.rng.choice(options), 0.0



    def states(self) -> Dict[str, Dict]:

        out = {}

        for pid, ped in self.peds.items():

            pos, heading = self._pose(ped)

            out[pid] = {"position": pos, "speed": ped["speed"], "acceleration": 0.0, "heading": heading,

                        "lane_id": "sidewalk", "vehicle_type": "pedestrian"}

        return out
