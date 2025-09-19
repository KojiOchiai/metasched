import asyncio
import logging
from pathlib import Path

from .maholo_api import client, schemas
from .maholo_api.client import BioportalClientError
from .settings import maholo_settings

logger = logging.getLogger("maholo_driver")
logger.setLevel(logging.INFO)


class DriverError(Exception):
    def __init__(self, message):
        super().__init__(message)


class FatalDriverError(DriverError):
    def __init__(self, message):
        super().__init__(message)


class Driver:
    async def move(self, what: str, from_: str, to: str):
        raise NotImplementedError

    async def run(self, protocol: str) -> list[str] | None:
        raise NotImplementedError


class DummyDriver(Driver):
    async def move(self, what: str, from_: str, to: str):
        pass

    async def run(self, protocol: str):
        pass


class MaholoDriver(Driver):
    microscope_image_dir: Path
    base_path: str
    max_retries = 10

    def __init__(
        self,
        host: str = "localhost",
        port: int = 63001,
        base_path: str = "C:\\BioApl\\DataSet\\proteo-03\\Protocol\\",
        microscope_image_dir: str = "./nikon_save/",
    ):
        self.client = client.BioportalClient(host, port)
        self.base_path = base_path
        self.microscope_image_dir = Path(microscope_image_dir)

    def path_replace(self, path: str) -> str:
        return path.replace("/", "#")

    async def move(self, what: str, from_: str, to: str):
        from_ = self.path_replace(from_)
        to = self.path_replace(to)
        try:
            async with self.client as client:
                await self._run(client, f"move_{what}_{from_}_{to}")
        except BioportalClientError:
            raise FatalDriverError("Connection to maholo failed")

    async def run(self, protocol: str) -> list[str] | None:
        try:
            async with self.client as client:
                await self._run(client, protocol)
        except BioportalClientError:
            raise FatalDriverError("Connection to maholo failed")
        if "getimage" in protocol:
            image_dirs = list(self.microscope_image_dir.glob("*/tiling/"))
            if len(image_dirs) == 0:
                raise DriverError("No image directory found")
            image_dir = sorted(image_dirs)[-1]
            file_paths = image_dir.glob("*.tif")
            return [str(fp) for fp in file_paths]
        return None

    async def get_status(self):
        async with self.client as client:
            await client.request_status()
            return await self._wait_response(client, schemas.GetStatusResponse)

    async def get_protocol_paths(self):
        async with self.client as client:
            return await self._get_protocol_paths(client)

    async def _run(
        self, client: client.BioportalClient, protocol: str
    ) -> schemas.NotifyStatusResponse:
        protocol_paths = await self._get_protocol_paths(client)
        if self.base_path + protocol not in protocol_paths:
            raise DriverError(f"protocol {protocol} not found in maholo")
        await self._wait_until_idle(client)
        await client.execute_protocol(self.base_path + protocol)  # start protocol
        exe_res: schemas.ExecuteProtocolResponse = await client.recv()
        match exe_res.Data.error_code:
            case "":
                pass
            case "403":
                raise DriverError("not set in external remote")
            case "404":
                raise DriverError("protocol not found")
            case "409":
                raise DriverError("other protocol is running")
            case "503":
                raise FatalDriverError("in alarm")
        res = await self._wait_complete(client)
        return res

    async def _get_protocol_paths(self, client: client.BioportalClient):
        await client.request_protocol_paths()
        for i in range(self.max_retries):
            res = await client.recv()
            if isinstance(res, schemas.GetProtocolPathsResponse):
                break
        return res.Data

    async def _wait_complete(self, client: client.BioportalClient):
        for i in range(self.max_retries):
            res = await client.recv()
            if isinstance(res, schemas.NotifyStatusResponse):
                if res.Data.exp_status == "completed":
                    return res
        raise DriverError("Failed to get response")

    async def _wait_until_idle(self, client: client.BioportalClient):
        while True:
            await client.request_status()
            res = await self._wait_response(client, schemas.GetStatusResponse)
            state = res.Data
            if state.is_idle():
                return res
            await asyncio.sleep(1)

    async def _wait_response(
        self, client: client.BioportalClient, response_type: type, max_retries: int = 10
    ):
        for i in range(max_retries):
            res = await client.recv()
            if isinstance(res, response_type):
                return res
        raise DriverError("Failed to get response")


driver = MaholoDriver(
    host=maholo_settings.host,
    port=maholo_settings.port,
    base_path=maholo_settings.base_path,
    microscope_image_dir=maholo_settings.microscope_image_dir,
)


async def execute_task_maholo(task_name: str) -> list[str] | None:
    logger.info(
        {"function": "execute_task_maholo", "type": "start", "task_name": task_name}
    )
    result = await driver.run(task_name)
    logger.info(
        {
            "function": "execute_task_maholo",
            "type": "end",
            "task_name": task_name,
            "result": result,
        }
    )
    return result
