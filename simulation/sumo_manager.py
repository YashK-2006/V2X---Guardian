import sys

import os

import logging

from typing import List, Dict, Any, Tuple, Optional



from config import get_config



logger = logging.getLogger(__name__)



try:

    import traci

    import traci.constants as tc

    import sumolib

    SUMO_AVAILABLE = True

except ImportError:

    SUMO_AVAILABLE = False

    logger.warning("SUMO (traci/sumolib) is not installed or not in PYTHONPATH.")



class SumoManager:

    """Manages SUMO lifecycle and provides data access using TraCI."""



    def __init__(self, config_file: str, gui: bool = False):

        self.cfg = get_config()

        self.config_file = config_file

        self.gui = gui

        self._is_running = False

        self._step_count = 0

        self.arrived: List[str] = []

        self._static: Dict[str, Dict[str, Any]] = {}



        # Verify SUMO is available

        if not SUMO_AVAILABLE:

            raise RuntimeError(

                "SUMO Python tools (traci, sumolib) are not available. "

                "Ensure SUMO is installed and SUMO_HOME is set."

            )



        # Set SUMO_HOME if not already set

        if "SUMO_HOME" not in os.environ:

            os.environ["SUMO_HOME"] = self.cfg.simulation.sumo_home



        # Add SUMO tools to path

        tools = os.path.join(os.environ["SUMO_HOME"], "tools")

        if tools not in sys.path:

            sys.path.append(tools)



    @property

    def is_running(self) -> bool:

        return self._is_running



    def start(self):

        """Starts the SUMO simulation."""

        binary = "sumo-gui" if self.gui else "sumo"

        sumo_binary = sumolib.checkBinary(binary)



        cmd = [

            sumo_binary,

            "-c", self.config_file,

            "--step-length", str(self.cfg.simulation.step_length),

            "--no-step-log", "true",

            "--no-warnings", "true",

        ]

        if self.gui:

            cmd += ["--start", "--quit-on-end"]



        port = self.cfg.simulation.sumo_port



        try:

            traci.start(cmd)

            self._is_running = True

            logger.info(f"Started SUMO via TraCI on port {port} (GUI: {self.gui})")

        except Exception as e:

            logger.error(f"Failed to start SUMO: {e}")

            raise



    def stop(self):

        """Stops the SUMO simulation gracefully."""

        if self._is_running:

            try:

                traci.close()

                logger.info("Closed SUMO TraCI connection.")

            except Exception:

                pass

            self._is_running = False



    def step(self) -> float:

        """Advances the simulation by one step. Returns the current simulation time."""

        if not self._is_running:

            raise RuntimeError("SUMO is not running.")



        traci.simulationStep()

        self._step_count += 1



        self.arrived = list(traci.simulation.getArrivedIDList())

        for vid in self.arrived:

            self._static.pop(vid, None)



        # Subscribe new vehicles

        new_vehicles = traci.simulation.getDepartedIDList()

        for vid in new_vehicles:

            try:

                self._static[vid] = {

                    "vehicle_type": traci.vehicle.getTypeID(vid),

                    "vehicle_class": traci.vehicle.getVehicleClass(vid),

                    "route": list(traci.vehicle.getRoute(vid)),

                    "length": traci.vehicle.getLength(vid),

                }

            except traci.exceptions.TraCIException:

                pass

            traci.vehicle.subscribe(vid, (

                tc.VAR_POSITION,

                tc.VAR_SPEED,

                tc.VAR_ACCEL,

                tc.VAR_ANGLE,

                tc.VAR_LANE_ID,

                tc.VAR_ROAD_ID

            ))



        return traci.simulation.getTime()



    def get_vehicle_ids(self) -> List[str]:

        """Returns a list of all active vehicle IDs."""

        if not self._is_running:

            return []

        return list(traci.vehicle.getIDList())



    def get_vehicle_state(self, vid: str) -> Dict[str, Any]:

        """Returns the state of a specific vehicle."""

        if not self._is_running:

            return {}



        try:

            res = traci.vehicle.getSubscriptionResults(vid)

            if not res:

                # Fallback if not subscribed

                return {

                    "position": traci.vehicle.getPosition(vid),

                    "speed": traci.vehicle.getSpeed(vid),

                    "acceleration": traci.vehicle.getAcceleration(vid),

                    "heading": traci.vehicle.getAngle(vid),

                    "lane_id": traci.vehicle.getLaneID(vid),

                    "road_id": traci.vehicle.getRoadID(vid),

                    **self._static.get(vid, {}),

                }



            return {

                "position": res[tc.VAR_POSITION],

                "speed": res[tc.VAR_SPEED],

                "acceleration": res.get(tc.VAR_ACCEL, 0.0),

                "heading": res[tc.VAR_ANGLE],

                "lane_id": res[tc.VAR_LANE_ID],

                "road_id": res[tc.VAR_ROAD_ID],

                **self._static.get(vid, {}),

            }

        except traci.exceptions.TraCIException:

            return {}



    def get_all_vehicle_states(self) -> Dict[str, Dict[str, Any]]:

        """Returns the states of all active vehicles."""

        if not self._is_running:

            return {}



        states = {}

        for vid in self.get_vehicle_ids():

            state = self.get_vehicle_state(vid)

            if state:

                states[vid] = state

        return states



    def get_sim_time(self) -> float:

        return traci.simulation.getTime() if self._is_running else 0.0



    def is_finished(self) -> bool:

        """True when all vehicles have left and no more are scheduled."""

        if not self._is_running:

            return True

        return traci.simulation.getMinExpectedNumber() <= 0



    def __enter__(self):

        self.start()

        return self



    def __exit__(self, exc_type, exc_val, exc_tb):

        self.stop()
