import copy
import socket
from pathlib import PureWindowsPath
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# Cookie


class BaseCookie(BaseModel):
    Group: str = "Remote"
    Name: str = Field(default_factory=socket.gethostname)
    To: str = "Service"

    def to_cookie(self) -> dict:
        cookies = (f"Group={self.Group}", f"Name={self.Name}", f"To={self.To}")
        return {"Cookie": "; ".join(cookies)}


class ConnectionCookie(BaseCookie):
    pass


class ServiceCookie(BaseCookie):
    @computed_field  # type: ignore
    @property
    def From(self) -> str:
        return f"{self.Name}@{self.Group}"

    def to_cookie(self) -> dict:
        cookies = (
            f"Group={self.Group}",
            f"Name={self.Name}",
            f"To={self.To}From={self.From}",
        )
        return {"Cookie": "; ".join(cookies)}


# BioPortalStatus

Mode = Literal["standard", "reservation", "external_remote"]
CellStatus = Literal["idle", "experiment"]
RobotPos = Literal["origin", "not_origin"]
ExpStatus = Literal["none", "requested", "running", "pause", "completed", "aborted"]


class BioPortalStatus(BaseModel):
    mode: Mode
    cell_status: CellStatus
    alarms: list[str]
    robot_pos: RobotPos
    exp_status: ExpStatus
    protocol: str

    def is_idle(self) -> bool:
        return (
            self.mode == "external_remote"
            and self.cell_status == "idle"
            and self.robot_pos == "origin"
            and self.exp_status == "none"
        )

    def is_requested(self) -> bool:
        return (
            self.mode == "external_remote"
            and self.cell_status == "experiment"
            and self.robot_pos == "origin"
            and self.exp_status == "requested"
        )

    def is_running(self) -> bool:
        return (
            self.mode == "external_remote"
            and self.cell_status == "experiment"
            and self.exp_status == "running"
        )

    def request(self, protocol: str):
        if not self.is_idle():
            raise ValueError("Not idle")
        self.cell_status = "experiment"
        self.exp_status = "requested"
        self.protocol = protocol
        return self

    def run(self):
        if not self.is_requested():
            raise ValueError("Not requested")
        self.robot_pos = "not_origin"
        self.exp_status = "running"
        return self

    def complete(self) -> "BioPortalStatus":
        if not self.is_running():
            raise ValueError("Not running")
        self.cell_status = "idle"
        self.robot_pos = "origin"
        self.exp_status = "none"
        self.protocol = ""

        res = copy.deepcopy(self)
        res.exp_status = "completed"
        return res

    @property
    def protocol_path(self) -> PureWindowsPath:
        return PureWindowsPath(self.protocol)


# ProtocolStatus

ErrorCode = Literal["", "403", "404", "409", "503"]


class ProtocolStatus(BaseModel):
    protocol: str
    error_code: ErrorCode
    error_message: str


# ProtocolExecutionCommand


class ProtocolExecutionData(BaseModel):
    protocol: str
    notified_user: str


# Request


class BaseRequest(BaseModel):
    From: str
    To: str = "Service"


class GetProtocolPathsRequest(BaseRequest):
    Command: Literal["GetProtocolPathes"] = "GetProtocolPathes"
    Data: None = None


class GetStatusRequest(BaseRequest):
    Command: Literal["GetStatus"] = "GetStatus"
    Data: None = None


class ExecuteProtocolRequest(BaseRequest):
    Data: ProtocolExecutionData
    Command: Literal["ExecuteProtocol"] = "ExecuteProtocol"


RequestType = GetProtocolPathsRequest | GetStatusRequest | ExecuteProtocolRequest


class AnyRequest(BaseModel):
    request: RequestType


def parse_request(data) -> RequestType:
    return AnyRequest(request=data).request


# Response

KindType = Literal["Request", "Response", "Notify"]
ResponseStatus = Literal["OK", "NG"]


class BaseResponse(BaseModel):
    To: str
    From: str = "Service"
    Kind: KindType = "Response"
    Status: ResponseStatus = "OK"
    Fin: bool = True


class NotifyUsersResponse(BaseResponse):
    Data: dict
    Command: Literal["NotifyUsers"] = "NotifyUsers"


class NotifyStatusResponse(BaseResponse):
    Data: BioPortalStatus
    Command: Literal["NotifyStatus"] = "NotifyStatus"


class GetProtocolPathsResponse(BaseResponse):
    Data: list[str]
    Command: Literal["GetProtocolPathes"] = "GetProtocolPathes"


class GetStatusResponse(BaseResponse):
    Data: BioPortalStatus
    Command: Literal["GetStatus"] = "GetStatus"


class ExecuteProtocolResponse(BaseResponse):
    Data: ProtocolStatus
    Command: Literal["ExecuteProtocol"] = "ExecuteProtocol"


ResponseType = (
    NotifyUsersResponse
    | NotifyStatusResponse
    | GetProtocolPathsResponse
    | GetStatusResponse
    | ExecuteProtocolResponse
)


class AnyResponse(BaseModel):
    response: ResponseType


def parse_response(
    data: NotifyStatusResponse | GetStatusResponse | ExecuteProtocolResponse,
) -> ResponseType:
    return AnyResponse(response=data).response


if __name__ == "__main__":
    p = GetProtocolPathsResponse(To="user", Data=["protocol1", "protocol2"])
    print(p)
