import json

from typing import List, Optional, Dict, Any

from datetime import datetime

from pydantic import BaseModel, Field

from sqlalchemy import Column, String, Float, Integer, JSON, DateTime, ForeignKey, Text

from sqlalchemy.orm import declarative_base, relationship



Base = declarative_base()



# ---------------------------------------------------------

# Pydantic Response Models

# ---------------------------------------------------------



class VehicleResponse(BaseModel):

    id: str

    hash: str

    position: List[float]  # [x, y]

    speed: float

    heading: float

    lane: str

    trust_score: float

    reputation: float

    status: str

    behavior_type: str

    message_count: int

    misbehavior_count: int



class VehicleDetailResponse(VehicleResponse):

    trust_history: List[Dict[str, Any]]

    behavior_history: List[Dict[str, Any]]

    ai_scores: Dict[str, float]

    blockchain_records: List[Dict[str, Any]]



class TrustResponse(BaseModel):

    vehicle_id: str

    score: float

    components: Dict[str, float]

    history: List[Dict[str, Any]]



class EventResponse(BaseModel):

    event_id: str

    type: str

    vehicle_id: str

    timestamp: float

    description: str

    severity: str

    ai_score: Optional[float] = None

    trust_impact: Optional[float] = None



class BlockchainStatusResponse(BaseModel):

    connected: bool

    blocks: int

    transactions: int

    validators: int

    latest_block_hash: str

    storage_bytes: int



class TransactionResponse(BaseModel):

    tx_id: str

    type: str

    vehicle_hash: str

    event_type: str

    score: float

    trust_before: float

    trust_after: float

    timestamp: float

    rsu: str



class BlockResponse(BaseModel):

    index: int

    hash: str

    prev_hash: str

    timestamp: float

    tx_count: int

    validator: str

    transactions: List[TransactionResponse]



class MetricsResponse(BaseModel):

    ai_metrics: Dict[str, Any]

    trust_metrics: Dict[str, Any]

    blockchain_metrics: Dict[str, Any]

    v2x_metrics: Dict[str, Any]

    simulation_metrics: Dict[str, Any]



class NetworkStatusResponse(BaseModel):

    simulation_running: bool

    sim_time: float

    vehicle_count: int

    trusted: int

    suspicious: int

    misbehaving: int

    messages_total: int

    blockchain_blocks: int

    blockchain_txs: int



class SimulationConfigRequest(BaseModel):

    num_vehicles: Optional[int] = None

    misbehavior_ratio: Optional[float] = None

    duration: Optional[int] = None

    scenario: Optional[str] = None



class ExperimentRequest(BaseModel):

    scenario_name: str

    config_overrides: Dict[str, Any] = Field(default_factory=dict)



# ---------------------------------------------------------

# SQLAlchemy Models

# ---------------------------------------------------------



class VehicleDB(Base):

    __tablename__ = "vehicles"

    vehicle_id = Column(String, primary_key=True, index=True)

    hash = Column(String, unique=True, index=True)

    behavior_type = Column(String)

    created_at = Column(DateTime, default=datetime.utcnow)



class MessageDB(Base):

    __tablename__ = "messages"

    message_id = Column(String, primary_key=True, index=True)

    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"))

    type = Column(String)

    timestamp = Column(Float)

    data_json = Column(JSON)



class EventDB(Base):

    __tablename__ = "events"

    event_id = Column(String, primary_key=True, index=True)

    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"))

    event_type = Column(String)

    severity = Column(String)

    ai_score = Column(Float, nullable=True)

    trust_impact = Column(Float, nullable=True)

    timestamp = Column(Float)



class TrustHistoryDB(Base):

    __tablename__ = "trust_history"

    id = Column(Integer, primary_key=True, autoincrement=True)

    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"))

    old_score = Column(Float)

    new_score = Column(Float)

    reason = Column(String)

    timestamp = Column(Float)



class ExperimentRunDB(Base):

    __tablename__ = "experiment_runs"

    run_id = Column(String, primary_key=True, index=True)

    scenario = Column(String)

    config_json = Column(JSON)

    start_time = Column(DateTime, default=datetime.utcnow)

    end_time = Column(DateTime, nullable=True)

    results_json = Column(JSON, nullable=True)





# ---------------------------------------------------------

# Live pipeline tables (written in batches by the API broadcaster)

# ---------------------------------------------------------



class MessageLogDB(Base):

    """Flagged and emergency V2X messages (full history is kept in memory per receiver)."""

    __tablename__ = "message_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(String, index=True)

    msg_id = Column(String, index=True)

    time = Column(Float, index=True)

    sender = Column(String, index=True)

    accused = Column(String, index=True, nullable=True)

    type = Column(String)

    content = Column(String)

    classification = Column(String, index=True)

    attack_type = Column(String)

    probability = Column(Float)

    sender_trust = Column(Float)

    tx_id = Column(String, nullable=True)

    data_json = Column(JSON)





class EvidenceDB(Base):

    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(String, index=True)

    attack_id = Column(String, index=True)

    vehicle_id = Column(String, index=True)

    attack_type = Column(String)

    time = Column(Float)

    hash = Column(String)

    tx_id = Column(String, nullable=True)

    record_json = Column(JSON)





class AlertDB(Base):

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(String, index=True)

    alert_id = Column(String)

    time = Column(Float)

    severity = Column(String)

    kind = Column(String)

    vehicle_id = Column(String, index=True)

    title = Column(String)

    message = Column(Text)

    details_json = Column(JSON)





class TrustEventDB(Base):

    __tablename__ = "trust_events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_id = Column(String, index=True)

    vehicle_id = Column(String, index=True)

    old_score = Column(Float)

    new_score = Column(Float)

    reason = Column(String)

    kind = Column(String)

    attack_type = Column(String, nullable=True)

    timestamp = Column(Float)
