import asyncio

import logging

from typing import List, Dict, Any

from fastapi import WebSocket, WebSocketDisconnect

import orjson



logger = logging.getLogger(__name__)



class ConnectionManager:

    def __init__(self):

        self.active_connections: List[WebSocket] = []



    async def connect(self, websocket: WebSocket):

        await websocket.accept()

        self.active_connections.append(websocket)

        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")



    def disconnect(self, websocket: WebSocket):

        if websocket in self.active_connections:

            self.active_connections.remove(websocket)

            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")



    async def send_to(self, websocket: WebSocket, data: dict):

        try:

            await websocket.send_text(orjson.dumps(data).decode('utf-8'))

        except Exception as e:

            logger.error(f"Error sending message to websocket: {e}")

            self.disconnect(websocket)



    async def broadcast(self, data: dict):

        if not self.active_connections:

            return



        json_data = orjson.dumps(data).decode('utf-8')

        disconnected = []

        for connection in self.active_connections:

            try:

                await connection.send_text(json_data)

            except WebSocketDisconnect:

                disconnected.append(connection)

            except Exception as e:

                logger.error(f"Error broadcasting to connection: {e}")

                disconnected.append(connection)



        for conn in disconnected:

            self.disconnect(conn)



    async def broadcast_json(self, data: dict):

        await self.broadcast(data)
