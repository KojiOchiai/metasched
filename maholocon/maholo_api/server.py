import json
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from maholocon.maholo_api import model, schemas

logger = logging.getLogger("maholosim")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


app = FastAPI()


protocol_model = model.ProtocolModel()
status = schemas.BioPortalStatus(
    mode="external_remote",
    cell_status="idle",
    alarms=[],
    robot_pos="origin",
    exp_status="none",
    protocol="",
)


def set_protocol_model(new_model: model.ProtocolModel):
    global protocol_model
    protocol_model = new_model


def get_protocol_paths() -> list[str]:
    return protocol_model.protocols


def get_status() -> schemas.BioPortalStatus:
    return status


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, name: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[name] = websocket

    def disconnect(self, name: str):
        if name in self.active_connections:
            self.active_connections.pop(name)

    async def send_text(self, to: str, message: str):
        if to not in self.active_connections:
            raise HTTPException(status_code=400, detail=f"Name {to} is not connected")
        await self.active_connections[to].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)


manager = ConnectionManager()


async def execute_protocol(data: schemas.ProtocolExecutionData):
    if status.mode != "external_remote":
        logger.error("Remote execution is currently forbidden")
        yield schemas.ProtocolStatus(
            protocol=data.protocol,
            error_code="403",
            error_message="Remote execution is currently forbidden",
        )
        return
    if data.protocol not in protocol_model.protocols:
        logger.error(f"Protocol not found: {data.protocol}")
        yield schemas.ProtocolStatus(
            protocol=data.protocol, error_code="404", error_message="Protocol not found"
        )
        return
    elif status.cell_status != "idle":
        logger.error("Not idle")
        yield schemas.ProtocolStatus(
            protocol=data.protocol, error_code="409", error_message="Not idle"
        )
        return
    elif len(status.alarms) > 0:
        logger.error("Alarms are active")
        yield schemas.ProtocolStatus(
            protocol=data.protocol, error_code="503", error_message="Alarms are active"
        )
        return
    yield schemas.ProtocolStatus(
        protocol=data.protocol, error_code="", error_message=""
    )

    yield status.request(data.protocol)
    yield status.run()
    try:
        await protocol_model.hook(status)
    except Exception as e:
        yield schemas.ProtocolStatus(
            protocol=data.protocol, error_code="503", error_message=str(e)
        )
        return

    yield status.complete()


@app.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    cookie_ = websocket.cookies
    if cookie_ is None:
        raise HTTPException(status_code=400, detail="Cookie is required")
    cookie = schemas.ConnectionCookie.model_validate(cookie_)
    data: Any = {}
    name = cookie.Name
    to = f"{cookie.Name}@{cookie.Group}"
    response: schemas.BaseResponse = schemas.NotifyUsersResponse(To=to, Data=data)

    await manager.connect(cookie.Name, websocket)
    await websocket.send_text(response.model_dump_json())
    try:
        while True:
            data = await websocket.receive_text()
            request = schemas.parse_request(json.loads(data))

            if isinstance(request, schemas.ExecuteProtocolRequest):
                logger.info(f"execute_protocol: {request.Data.protocol}")
                async for data in execute_protocol(request.Data):
                    if isinstance(data, schemas.BioPortalStatus):
                        logger.info("notify_status: " + data.exp_status)
                        response = schemas.NotifyStatusResponse(To=to, Data=data)
                        await manager.send_text(name, response.model_dump_json())
                    elif isinstance(data, schemas.ProtocolStatus):
                        logger.info("execute_protocol_response")
                        response = schemas.ExecuteProtocolResponse(To=to, Data=data)
                        await manager.send_text(name, response.model_dump_json())
            else:
                if isinstance(request, schemas.GetProtocolPathsRequest):
                    logger.info("get_protocol_paths")
                    data = get_protocol_paths()
                    response = schemas.GetProtocolPathsResponse(To=to, Data=data)
                elif isinstance(request, schemas.GetStatusRequest):
                    logger.info("get_status")
                    data = get_status()
                    response = schemas.GetStatusResponse(To=to, Data=data)
                else:
                    raise HTTPException(status_code=400, detail="Invalid request")
                await websocket.send_text(response.model_dump_json())
    except (WebSocketDisconnect, ConnectionClosedOK, ConnectionClosedError) as e:
        logger.debug(f"websocket {name} disconnected {e}")
        manager.disconnect(name)
