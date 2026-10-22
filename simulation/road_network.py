import os

import sys

import subprocess

import logging

from typing import Dict, Any



from config import get_config



logger = logging.getLogger(__name__)





# Vehicle types used across the simulation. Keys are SUMO vType ids; values are

# (vClass, guiShape, color, length, maxSpeed, probability in the mixed distribution).

VEHICLE_TYPES: Dict[str, Dict[str, Any]] = {

    "car":        {"vClass": "passenger",  "guiShape": "passenger",          "color": "0.8,0.8,0.8", "length": 4.5,  "maxSpeed": 50.0, "probability": 0.44},

    "suv":        {"vClass": "passenger",  "guiShape": "passenger/van",      "color": "0.4,0.6,0.9", "length": 5.0,  "maxSpeed": 45.0, "probability": 0.14},

    "taxi":       {"vClass": "taxi",       "guiShape": "passenger/sedan",    "color": "1,0.85,0",    "length": 4.6,  "maxSpeed": 45.0, "probability": 0.10},

    "bus":        {"vClass": "bus",        "guiShape": "bus",                "color": "0.2,0.7,0.3", "length": 12.0, "maxSpeed": 25.0, "probability": 0.06},

    "truck":      {"vClass": "truck",      "guiShape": "truck",              "color": "0.6,0.4,0.2", "length": 9.0,  "maxSpeed": 25.0, "probability": 0.08},

    "motorcycle": {"vClass": "motorcycle", "guiShape": "motorcycle",         "color": "0.9,0.3,0.9", "length": 2.2,  "maxSpeed": 50.0, "probability": 0.09},

    "ambulance":  {"vClass": "emergency",  "guiShape": "emergency",          "color": "1,1,1",       "length": 6.0,  "maxSpeed": 50.0, "probability": 0.03},

    "firetruck":  {"vClass": "emergency",  "guiShape": "firebrigade",        "color": "1,0,0",       "length": 8.0,  "maxSpeed": 40.0, "probability": 0.02},

    "police":     {"vClass": "authority",  "guiShape": "police",             "color": "0,0,1",       "length": 4.8,  "maxSpeed": 55.0, "probability": 0.04},

}



EMERGENCY_TYPES = {"ambulance", "firetruck", "police"}



NET_FILE = "grid.net.xml"

VTYPES_FILE = "vtypes.add.xml"

ROUTE_FILE = "routes.rou.xml"

CONFIG_FILE = "simulation.sumocfg"





class RoadNetworkGenerator:

    """Generates SUMO road networks, vehicle types, routes, and config files."""



    def __init__(self):

        self.cfg = get_config()

        self.sumo_home = os.environ.get("SUMO_HOME", self.cfg.simulation.sumo_home)



        if not os.path.exists(self.sumo_home):

            logger.warning(f"SUMO_HOME not found at {self.sumo_home}. Ensure SUMO is installed.")



    def _run_command(self, cmd: list) -> bool:

        """Helper to run shell commands."""

        try:

            logger.info(f"Running command: {' '.join(cmd)}")

            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            logger.debug(result.stdout)

            return True

        except subprocess.CalledProcessError as e:

            logger.error(f"Command failed: {e}\n{e.stderr}")

            return False



    def _binary(self, name: str) -> str:

        path = os.path.join(self.sumo_home, "bin", name)

        if os.name == 'nt' and not path.endswith('.exe'):

            path += ".exe"

        return path



    def generate_grid_network(self, output_dir: str, grid_size: int, edge_length: float, num_lanes: int, speed_limit: float) -> str:

        """Runs netgenerate to create a grid network."""

        os.makedirs(output_dir, exist_ok=True)

        net_file = os.path.join(output_dir, NET_FILE)



        cmd = [

            self._binary("netgenerate"),

            "--grid",

            "--grid.number", str(grid_size),

            "--grid.length", str(edge_length),

            "--default.lanenumber", str(num_lanes),

            "--default.speed", str(speed_limit),

            "--output-file", net_file,

            "--tls.guess", "true"

        ]



        if self._run_command(cmd):

            return net_file

        raise RuntimeError("Failed to generate grid network.")



    def generate_vehicle_types(self, output_dir: str, type_mix: Dict[str, float] = None) -> str:

        """Writes the vType definitions and a 'mix' vTypeDistribution."""

        os.makedirs(output_dir, exist_ok=True)

        vtypes_file = os.path.join(output_dir, VTYPES_FILE)

        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<additional>", '    <vTypeDistribution id="mix">']

        for type_id, t in VEHICLE_TYPES.items():

            prob = (type_mix or {}).get(type_id, t["probability"])

            lines.append(

                f'        <vType id="{type_id}" vClass="{t["vClass"]}" guiShape="{t["guiShape"]}" '

                f'color="{t["color"]}" length="{t["length"]}" maxSpeed="{t["maxSpeed"]}" '

                f'lcStrategic="1.0" lcCooperative="1.0" lcSpeedGain="1.0" probability="{prob}"/>'

            )

        lines += ["    </vTypeDistribution>", "</additional>", ""]

        with open(vtypes_file, "w") as f:

            f.write("\n".join(lines))

        return vtypes_file



    def generate_routes(self, net_file: str, output_dir: str, num_vehicles: int, duration: int,

                        vtypes_file: str = None, period: float = 1.5, seed: int = 42) -> str:

        """Runs randomTrips.py to create routes using the mixed vehicle type distribution."""

        route_file = os.path.join(output_dir, ROUTE_FILE)

        random_trips = os.path.join(self.sumo_home, "tools", "randomTrips.py")



        trip_attrs = 'departLane="best" departSpeed="max" departPos="random"'

        if vtypes_file:

            trip_attrs += ' type="mix"'



        cmd = [

            sys.executable, random_trips,

            "-n", net_file,

            "-e", str(duration),

            "-p", str(period),

            "-r", route_file,

            "-o", os.path.join(output_dir, "trips.trips.xml"),

            "--seed", str(seed),

            "--trip-attributes", trip_attrs,

            "--fringe-factor", "10",

            "--validate",

        ]

        if vtypes_file:

            cmd += ["-a", vtypes_file]



        if self._run_command(cmd):

            return route_file

        raise RuntimeError("Failed to generate routes.")



    def generate_sumo_config(self, net_file: str, route_file: str, output_dir: str, step_length: float,

                             duration: int, vtypes_file: str = None) -> str:

        """Creates the .sumocfg file."""

        config_file = os.path.join(output_dir, CONFIG_FILE)

        additional = f'\n        <additional-files value="{os.path.basename(vtypes_file)}"/>' if vtypes_file else ""



        config_content = f"""<?xml version="1.0" encoding="UTF-8"?>

<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">

    <input>

        <net-file value="{os.path.basename(net_file)}"/>

        <route-files value="{os.path.basename(route_file)}"/>{additional}

    </input>

    <time>

        <begin value="0"/>

        <end value="{duration}"/>

        <step-length value="{step_length}"/>

    </time>

    <processing>

        <time-to-teleport value="-1"/>

    </processing>

    <report>

        <no-warnings value="true"/>

        <no-step-log value="true"/>

    </report>

</configuration>

"""

        with open(config_file, "w") as f:

            f.write(config_content)



        return config_file



    def setup_scenario(self, output_dir: str) -> str:

        """Convenience method to set up network, routes, and config."""

        sim = self.cfg.simulation

        net_file = self.generate_grid_network(output_dir, sim.grid_size, sim.grid_length, sim.num_lanes, sim.speed_limit)

        vtypes_file = self.generate_vehicle_types(output_dir)

        route_file = self.generate_routes(net_file, output_dir, sim.num_vehicles, sim.sim_duration, vtypes_file)

        # duarouter embeds the resolved vTypes into the route file, so no additional file is needed

        return self.generate_sumo_config(net_file, route_file, output_dir, sim.step_length, sim.sim_duration)



    def parse_network_geometry(self, net_file: str) -> Dict[str, Any]:

        """Extracts network geometry (edges, lanes, junctions, traffic lights) using sumolib."""

        import sumolib

        net = sumolib.net.readNet(net_file)



        bounds = net.getBBoxXY()



        edges = []

        for edge in net.getEdges():

            if edge.getFunction() == "internal":

                continue

            edges.append({

                "id": edge.getID(),

                "shape": edge.getShape(),

                "lanes": edge.getLaneNumber(),

            })



        junctions = []

        for node in net.getNodes():

            junctions.append({

                "id": node.getID(),

                "coord": node.getCoord(),

                "type": node.getType(),

            })



        traffic_lights = [tls.getID() for tls in net.getTrafficLights()]



        return {

            "bounds": {"min_x": bounds[0][0], "min_y": bounds[0][1], "max_x": bounds[1][0], "max_y": bounds[1][1]},

            "edges": edges,

            "junctions": junctions,

            "traffic_lights": traffic_lights,

        }
