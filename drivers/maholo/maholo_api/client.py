import json

import websockets

from . import schemas


class BioportalClientError(Exception):
    pass


class BioportalClient:
    host: str = "localhost"
    port: int = 63001
    cookie: schemas.ServiceCookie

    def __init__(self, host: str = "localhost", port: int = 63001):
        self.host = host
        self.port = port
        self.url = f"ws://{self.host}:{self.port}"

    async def __aenter__(self):
        cookie = schemas.ConnectionCookie()
        try:
            self.ws = await websockets.connect(
                self.url, additional_headers=cookie.to_cookie()
            )
        except OSError as e:
            raise BioportalClientError(f"Connection failed: {e}")
        self.cookie = schemas.ServiceCookie.model_validate(cookie.model_dump())
        res = await self.recv()
        if not isinstance(res, schemas.NotifyUsersResponse):
            raise Exception("Connection failed")
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.ws.close()

    async def recv(self):
        res = await self.ws.recv()
        respnse = schemas.parse_response(json.loads(res))
        return respnse

    async def request_protocol_paths(self):
        from_ = self.cookie.From
        path_request = schemas.GetProtocolPathsRequest(From=from_, Data=None)
        await self.ws.send(path_request.model_dump_json())

    async def request_status(self):
        from_ = self.cookie.From
        status_request = schemas.GetStatusRequest(From=from_, Data=None)
        await self.ws.send(status_request.model_dump_json())

    async def execute_protocol(self, protocol: str):
        name = self.cookie.Name
        from_ = self.cookie.From
        command = schemas.ProtocolExecutionData(protocol=protocol, notified_user=name)
        execute_request = schemas.ExecuteProtocolRequest(From=from_, Data=command)
        await self.ws.send(execute_request.model_dump_json())
