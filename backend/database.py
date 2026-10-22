import os

from contextlib import asynccontextmanager

from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from sqlalchemy.future import select

from sqlalchemy import desc



from backend.models import (Base, VehicleDB, MessageDB, EventDB, TrustHistoryDB, ExperimentRunDB,

                            MessageLogDB, EvidenceDB, AlertDB, TrustEventDB)



class Database:

    def __init__(self, database_url: str):

        # Ensure database directory exists if using sqlite

        if database_url.startswith("sqlite"):

            db_path = database_url.replace("sqlite+aiosqlite:///", "")

            if db_path:

                os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)



        self.engine = create_async_engine(database_url, echo=False)

        self.SessionLocal = async_sessionmaker(

            bind=self.engine,

            class_=AsyncSession,

            expire_on_commit=False,

        )



    async def init_db(self):

        """Create all tables in the database."""

        async with self.engine.begin() as conn:

            await conn.run_sync(Base.metadata.create_all)



    @asynccontextmanager

    async def get_session(self):

        """Provide a transactional scope around a series of operations."""

        session = self.SessionLocal()

        try:

            yield session

            await session.commit()

        except Exception:

            await session.rollback()

            raise

        finally:

            await session.close()



    async def log_event(self, event_data: Dict[str, Any]):

        async with self.get_session() as session:

            db_event = EventDB(

                event_id=event_data["event_id"],

                vehicle_id=event_data["vehicle_id"],

                event_type=event_data["type"],

                severity=event_data["severity"],

                ai_score=event_data.get("ai_score"),

                trust_impact=event_data.get("trust_impact"),

                timestamp=event_data["timestamp"]

            )

            session.add(db_event)



    async def log_trust_update(self, update_data: Dict[str, Any]):

        async with self.get_session() as session:

            db_update = TrustHistoryDB(

                vehicle_id=update_data["vehicle_id"],

                old_score=update_data["old_score"],

                new_score=update_data["new_score"],

                reason=update_data["reason"],

                timestamp=update_data["timestamp"]

            )

            session.add(db_update)



    async def log_message(self, message_data: Dict[str, Any]):

        async with self.get_session() as session:

            db_msg = MessageDB(

                message_id=message_data["message_id"],

                vehicle_id=message_data["vehicle_id"],

                type=message_data["type"],

                timestamp=message_data["timestamp"],

                data_json=message_data.get("data", {})

            )

            session.add(db_msg)



    async def get_recent_events(self, count: int = 50) -> List[Dict[str, Any]]:

        async with self.get_session() as session:

            result = await session.execute(

                select(EventDB).order_by(desc(EventDB.timestamp)).limit(count)

            )

            events = result.scalars().all()

            return [

                {

                    "event_id": e.event_id,

                    "type": e.event_type,

                    "vehicle_id": e.vehicle_id,

                    "timestamp": e.timestamp,

                    "description": f"Event {e.event_type} for vehicle {e.vehicle_id}",

                    "severity": e.severity,

                    "ai_score": e.ai_score,

                    "trust_impact": e.trust_impact,

                }

                for e in events

            ]



    async def get_trust_history(self, vehicle_id: str) -> List[Dict[str, Any]]:

        async with self.get_session() as session:

            result = await session.execute(

                select(TrustHistoryDB)

                .where(TrustHistoryDB.vehicle_id == vehicle_id)

                .order_by(TrustHistoryDB.timestamp)

            )

            history = result.scalars().all()

            return [

                {

                    "id": h.id,

                    "vehicle_id": h.vehicle_id,

                    "old_score": h.old_score,

                    "new_score": h.new_score,

                    "reason": h.reason,

                    "timestamp": h.timestamp,

                }

                for h in history

            ]



    async def save_experiment_run(self, run_data: Dict[str, Any]):

        async with self.get_session() as session:

            run_db = ExperimentRunDB(

                run_id=run_data["run_id"],

                scenario=run_data["scenario"],

                config_json=run_data.get("config", {}),

                start_time=run_data.get("start_time"),

                end_time=run_data.get("end_time"),

                results_json=run_data.get("results", {})

            )

            session.add(run_db)



    async def get_experiment_results(self, run_id: str) -> Optional[Dict[str, Any]]:

        async with self.get_session() as session:

            result = await session.execute(

                select(ExperimentRunDB).where(ExperimentRunDB.run_id == run_id)

            )

            run = result.scalar_one_or_none()

            if run:

                return {

                    "run_id": run.run_id,

                    "scenario": run.scenario,

                    "config": run.config_json,

                    "start_time": run.start_time,

                    "end_time": run.end_time,

                    "results": run.results_json

                }

            return None



    async def write_pipeline_batch(self, run_id: str, batch: Dict[str, List[Dict[str, Any]]]):

        """Persist one batch of orchestrator output (trust events, evidence, alerts, flagged messages)."""

        if not any(batch.values()):

            return

        async with self.get_session() as session:

            for t in batch.get("trust", []):

                session.add(TrustEventDB(run_id=run_id, vehicle_id=t["vehicle_id"], old_score=t["old_score"],

                                         new_score=t["new_score"], reason=t["reason"], kind=t["kind"],

                                         attack_type=t.get("attack_type"), timestamp=t["timestamp"]))

            for e in batch.get("evidence", []):

                session.add(EvidenceDB(run_id=run_id, attack_id=e["attack_id"], vehicle_id=e["vehicle_id"],

                                       attack_type=e["attack_type"], time=e["time"], hash=e["hash"],

                                       tx_id=e.get("tx_id"), record_json=_jsonable(e)))

            for a in batch.get("alerts", []):

                session.add(AlertDB(run_id=run_id, alert_id=a["id"], time=a["time"], severity=a["severity"],

                                    kind=a["kind"], vehicle_id=a["vehicle_id"], title=a["title"],

                                    message=a["message"], details_json=_jsonable(a["details"])))

            for m in batch.get("messages", []):

                session.add(MessageLogDB(run_id=run_id, msg_id=m["msg_id"], time=m["time"], sender=m["sender"],

                                         accused=m.get("accused"), type=m["type"], content=m["content"],

                                         classification=m["classification"], attack_type=m["attack_type"],

                                         probability=m["probability"], sender_trust=m["sender_trust"],

                                         tx_id=m.get("tx_id"), data_json=_jsonable(m)))



    async def get_alerts(self, run_id: str, limit: int = 200) -> List[Dict[str, Any]]:

        async with self.get_session() as session:

            result = await session.execute(

                select(AlertDB).where(AlertDB.run_id == run_id).order_by(desc(AlertDB.time)).limit(limit))

            return [{"id": a.alert_id, "time": a.time, "severity": a.severity, "kind": a.kind,

                     "vehicle_id": a.vehicle_id, "title": a.title, "message": a.message,

                     "details": a.details_json} for a in result.scalars().all()]



    async def get_message_log(self, run_id: str, vehicle_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:

        async with self.get_session() as session:

            q = select(MessageLogDB).where(MessageLogDB.run_id == run_id)

            if vehicle_id:

                q = q.where((MessageLogDB.sender == vehicle_id) | (MessageLogDB.accused == vehicle_id))

            result = await session.execute(q.order_by(desc(MessageLogDB.time)).limit(limit))

            return [m.data_json for m in result.scalars().all()]





def _jsonable(obj):

    """Round-trip through JSON-safe types (tuples -> lists, unknown -> str)."""

    import json

    return json.loads(json.dumps(obj, default=str))
