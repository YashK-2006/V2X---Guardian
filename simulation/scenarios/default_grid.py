import os

from typing import Dict, Any, Optional



from config import get_config

from simulation.road_network import RoadNetworkGenerator, NET_FILE

from simulation.scenarios.presets import ScenarioPreset, get_scenario





class DefaultGridScenario:

    """Sets up a 4x4 grid scenario. Generated files are cached per preset and reused."""



    def __init__(self, preset: Optional[ScenarioPreset] = None):

        self.cfg = get_config()

        self.preset = preset or get_scenario("normal")

        self.generator = RoadNetworkGenerator()

        self.output_dir = os.path.join(self.cfg.simulation.output_dir, "scenarios", self.preset.id)

        self.config_path = None

        self.net_file = os.path.join(self.output_dir, NET_FILE)



    def setup(self, force: bool = False):

        """Generates network, vehicle types, routes and config (skipped when already cached)."""

        os.makedirs(self.output_dir, exist_ok=True)

        sim = self.cfg.simulation

        cfg_file = os.path.join(self.output_dir, "simulation.sumocfg")

        if os.path.exists(cfg_file) and os.path.exists(self.net_file) and not force:

            self.config_path = cfg_file

            return



        net_file = self.generator.generate_grid_network(

            self.output_dir, sim.grid_size, sim.grid_length, sim.num_lanes, sim.speed_limit

        )

        vtypes_file = self.generator.generate_vehicle_types(self.output_dir, self.preset.type_mix)

        route_file = self.generator.generate_routes(

            net_file, self.output_dir, sim.num_vehicles, sim.sim_duration, vtypes_file,

            period=self.preset.period, seed=self.preset.seed,

        )

        self.config_path = self.generator.generate_sumo_config(

            net_file, route_file, self.output_dir, sim.step_length, sim.sim_duration

        )



    def get_config_path(self) -> str:

        """Returns the path to the generated .sumocfg file."""

        if not self.config_path:

            raise RuntimeError("Scenario not set up yet. Call setup() first.")

        return self.config_path



    def get_scenario_params(self) -> Dict[str, Any]:

        """Returns parameters defining this scenario."""

        sim = self.cfg.simulation

        return {

            "id": self.preset.id,

            "name": self.preset.name,

            "grid_size": sim.grid_size,

            "edge_length": sim.grid_length,

            "departure_period": self.preset.period,

            "duration": sim.sim_duration,

            "step_length": sim.step_length,

        }
