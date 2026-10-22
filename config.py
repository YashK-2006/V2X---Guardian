"""

Central Configuration for V2X Blockchain AI Framework.



All parameters are configurable via environment variables or direct modification.

"""



import os

from dataclasses import dataclass, field

from typing import Dict, List, Optional





try:

    from dotenv import load_dotenv

    load_dotenv()

except ImportError:

    pass





import sys





def _get_default_sumo_home() -> str:

    home = os.environ.get("SUMO_HOME", "")

    if not home:

        try:

            import sumo

            if hasattr(sumo, "SUMO_HOME") and os.path.exists(sumo.SUMO_HOME):

                home = sumo.SUMO_HOME

        except ImportError:

            pass

    if home and os.path.exists(home):

        bin_dir = os.path.join(home, "bin")

        if os.path.exists(bin_dir) and bin_dir not in os.environ.get("PATH", ""):

            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")

        tools_dir = os.path.join(home, "tools")

        if os.path.exists(tools_dir) and tools_dir not in sys.path:

            sys.path.append(tools_dir)

    return home





@dataclass

class SimulationConfig:

    """SUMO simulation parameters."""

    # SUMO paths

    sumo_home: str = field(default_factory=_get_default_sumo_home)

    sumo_binary: str = os.environ.get("SUMO_BINARY", "sumo")  # "sumo-gui" for GUI mode

    sumo_port: int = int(os.environ.get("SUMO_PORT", "8813"))



    # Network generation

    network_type: str = "grid"  # "grid" or "spider" or "random"

    grid_size: int = 4  # NxN grid

    grid_length: float = 200.0  # Edge length in meters

    num_lanes: int = 2

    speed_limit: float = 13.89  # 50 km/h in m/s



    # Simulation timing

    step_length: float = 0.1  # Simulation step in seconds

    sim_duration: int = 3600  # Total simulation time in seconds

    warmup_steps: int = 100  # Steps before data collection starts



    # Vehicle generation

    num_vehicles: int = 100

    vehicle_spawn_rate: float = 0.8  # Vehicles per second

    misbehavior_ratio: float = 0.10  # 10% misbehaving vehicles



    # Output

    output_dir: str = os.path.join(os.path.dirname(__file__), "simulation", "output")





@dataclass

class VehicleConfig:

    """Vehicle model parameters."""

    # Identity

    id_prefix: str = "V"

    hash_algorithm: str = "sha256"



    # Physical constraints

    max_speed: float = 50.0  # m/s (~180 km/h)

    max_acceleration: float = 3.0  # m/s²

    max_deceleration: float = 8.0  # m/s²

    max_heading_change: float = 45.0  # degrees per second



    # Communication

    communication_range: float = 300.0  # meters

    cam_frequency: float = 10.0  # Hz (messages per second)

    denm_frequency: float = 1.0  # Hz



    # Sensor noise (for normal behavior)

    position_noise_std: float = 1.5  # meters (GPS accuracy)

    speed_noise_std: float = 0.5  # m/s

    heading_noise_std: float = 2.0  # degrees





@dataclass

class MisbehaviorConfig:

    """Synthetic misbehavior parameters."""

    # Position inconsistency

    position_offset_min: float = 50.0  # meters

    position_offset_max: float = 500.0



    # Speed inconsistency

    speed_offset_min: float = 10.0  # m/s

    speed_offset_max: float = 30.0



    # Acceleration inconsistency

    acceleration_offset: float = 10.0  # m/s²



    # False event reporting

    false_event_probability: float = 0.3  # per step

    false_event_types: List[str] = field(default_factory=lambda: [

        "ACCIDENT", "ROAD_HAZARD", "CONGESTION", "EMERGENCY"

    ])



    # Message frequency anomaly

    frequency_multiplier: float = 5.0  # times normal rate



    # Sudden behavioral change

    change_trigger_step: int = 500  # Step at which behavior changes



    # Sybil identity

    sybil_count: int = 3  # Number of fake identities





@dataclass

class AIConfig:

    """AI/ML model parameters."""

    # Feature extraction

    feature_window_size: int = 10  # Rolling window for temporal features



    # Model selection

    primary_model: str = "random_forest"  # "random_forest" or "xgboost"



    # Random Forest

    rf_n_estimators: int = 100

    rf_max_depth: Optional[int] = 15

    rf_min_samples_split: int = 5

    rf_min_samples_leaf: int = 2



    # XGBoost / Gradient Boosting

    xgb_n_estimators: int = 100

    xgb_max_depth: int = 6

    xgb_learning_rate: float = 0.1



    # Isolation Forest (anomaly detection)

    if_n_estimators: int = 100

    if_contamination: float = 0.1



    # Training

    test_split: float = 0.2

    validation_split: float = 0.1

    cross_validation_folds: int = 5

    random_seed: int = 42



    # Inference

    classification_threshold: float = 0.5

    anomaly_threshold: float = -0.5



    # Paths

    model_dir: str = os.path.join(os.path.dirname(__file__), "ai", "models")

    dataset_dir: str = os.path.join(os.path.dirname(__file__), "datasets")





@dataclass

class TrustConfig:

    """Trust management parameters."""

    # Trust weights (must sum to 1.0)

    alpha: float = 0.35  # AI behavior score weight

    beta: float = 0.25   # Neighbor consensus weight

    gamma: float = 0.25  # Historical reputation weight

    delta: float = 0.15  # Blockchain reputation weight



    # Trust bounds

    initial_trust: float = 0.5

    min_trust: float = 0.0

    max_trust: float = 1.0



    # Trust update rates

    trust_increase_rate: float = 0.02   # Per normal observation

    trust_decrease_minor: float = 0.05  # Minor anomaly

    trust_decrease_moderate: float = 0.15  # Moderate anomaly

    trust_decrease_severe: float = 0.30  # Confirmed misbehavior



    # Trust recovery

    recovery_enabled: bool = True

    recovery_rate: float = 0.01  # Per normal observation after misbehavior

    recovery_cooldown_steps: int = 100  # Steps before recovery can begin



    # Decision thresholds

    trust_threshold_accept: float = 0.75

    trust_threshold_verify: float = 0.50

    trust_threshold_downweight: float = 0.30

    trust_threshold_ignore: float = 0.15



    # Consensus

    consensus_min_neighbors: int = 2

    consensus_agreement_threshold: float = 0.6





@dataclass

class BlockchainConfig:

    """Blockchain network parameters."""

    # Network

    num_rsu_nodes: int = 4

    rsu_id_prefix: str = "RSU"



    # Block parameters

    block_size: int = 50  # Max transactions per block

    mining_interval: float = 5.0  # Seconds between blocks



    # Cryptography

    hash_algorithm: str = "sha256"

    signature_algorithm: str = "ECDSA"

    key_curve: str = "SECP256K1"



    # Consensus

    consensus_mechanism: str = "proof_of_authority"

    required_validators: int = 2  # Minimum validators for block confirmation



    # Storage

    ledger_dir: str = os.path.join(os.path.dirname(__file__), "blockchain", "data")



    # Performance

    max_pending_transactions: int = 1000

    transaction_timeout: float = 30.0  # Seconds





@dataclass

class BackendConfig:

    """Backend API parameters."""

    host: str = os.environ.get("API_HOST", "127.0.0.1")

    port: int = int(os.environ.get("API_PORT", "8000"))



    # WebSocket

    ws_broadcast_rate: float = 10.0  # Hz (updates per second)

    ws_max_connections: int = 50



    # Database

    database_url: str = os.environ.get(

        "DATABASE_URL",

        f"sqlite+aiosqlite:///{os.path.join(os.path.dirname(__file__), 'data', 'v2x.db')}"

    )



    # CORS

    cors_origins: List[str] = field(default_factory=lambda: [

        "http://localhost:5173",  # Vite dev server

        "http://localhost:3000",

        "http://127.0.0.1:5173",

    ])





@dataclass

class DashboardConfig:

    """Dashboard parameters."""

    dev_port: int = 5173

    api_base_url: str = "http://127.0.0.1:8000"

    ws_base_url: str = "ws://127.0.0.1:8000"





@dataclass

class ExperimentConfig:

    """Experiment parameters."""

    results_dir: str = os.path.join(os.path.dirname(__file__), "experiments", "results")

    configs_dir: str = os.path.join(os.path.dirname(__file__), "experiments", "configs")



    # Default experiment

    default_duration: int = 600  # 10 minutes simulation

    default_num_vehicles: int = 100

    default_misbehavior_ratio: float = 0.10

    num_repetitions: int = 3  # For statistical significance





@dataclass

class AppConfig:

    """Root application configuration."""

    simulation: SimulationConfig = field(default_factory=SimulationConfig)

    vehicle: VehicleConfig = field(default_factory=VehicleConfig)

    misbehavior: MisbehaviorConfig = field(default_factory=MisbehaviorConfig)

    ai: AIConfig = field(default_factory=AIConfig)

    trust: TrustConfig = field(default_factory=TrustConfig)

    blockchain: BlockchainConfig = field(default_factory=BlockchainConfig)

    backend: BackendConfig = field(default_factory=BackendConfig)

    dashboard: DashboardConfig = field(default_factory=DashboardConfig)

    experiment: ExperimentConfig = field(default_factory=ExperimentConfig)



    # Debug

    debug: bool = os.environ.get("V2X_DEBUG", "false").lower() == "true"

    log_level: str = os.environ.get("V2X_LOG_LEVEL", "INFO")





# Global configuration instance

config = AppConfig()





def get_config() -> AppConfig:

    """Get the global configuration instance."""

    return config





def validate_config(cfg: AppConfig) -> List[str]:

    """Validate configuration and return list of issues."""

    issues = []



    # Trust weights must sum to 1.0

    weight_sum = cfg.trust.alpha + cfg.trust.beta + cfg.trust.gamma + cfg.trust.delta

    if abs(weight_sum - 1.0) > 0.001:

        issues.append(

            f"Trust weights must sum to 1.0, got {weight_sum:.3f} "

            f"(α={cfg.trust.alpha}, β={cfg.trust.beta}, γ={cfg.trust.gamma}, δ={cfg.trust.delta})"

        )



    # Misbehavior ratio bounds

    if not 0.0 <= cfg.simulation.misbehavior_ratio <= 1.0:

        issues.append(f"Misbehavior ratio must be in [0, 1], got {cfg.simulation.misbehavior_ratio}")



    # Blockchain validators

    if cfg.blockchain.required_validators > cfg.blockchain.num_rsu_nodes:

        issues.append(

            f"Required validators ({cfg.blockchain.required_validators}) > "

            f"total RSU nodes ({cfg.blockchain.num_rsu_nodes})"

        )



    # Trust thresholds ordering

    t = cfg.trust

    if not (t.trust_threshold_accept > t.trust_threshold_verify >

            t.trust_threshold_downweight > t.trust_threshold_ignore):

        issues.append("Trust thresholds must be in descending order: accept > verify > downweight > ignore")



    return issues
