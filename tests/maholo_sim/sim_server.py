import asyncio
from datetime import datetime
from pathlib import Path

import uvicorn
from cv2 import imwrite

from drivers.maholo.maholo_api import schemas
from tests.maholo_sim import model, server
from tests.maholo_sim.microscope import nikon

WAIT_TIME = 1

IMAGE_DIR = Path("./nikon_save")
image = nikon.get_image(0.5)

IMAGE_DIR.mkdir(parents=True, exist_ok=True)


protocol_patterns = [
    # demo
    "scheduling_{1..5}",
    # getimage
    "getimage_plate6well_Co2Incubator#1#{1..8}",
    # move
    "move_tube1.5mL_Freezer#24_LifterStocker#12#12",
    # collection (min)
    "0min回収",
    "5min回収",
    "15min回収_前半",
    "15min回収_後半",
    "30min回収_前半",
    "30min回収_後半",
    "60min回収_前半",
    "60min回収_後半",
    "90min回収_前半",
    "90min回収_後半",
    "180min回収_前半",
    "180min回収_後半",
    "240min回収_前半",
    "240min回収_後半",
    # collection (sec)
    "0sec回収",
    "5sec回収",
    "15sec回収_前半",
    "15sec回収_後半",
    "30sec回収_前半",
    "30sec回収_後半",
    "60sec回収_前半",
    "60sec回収_後半",
    "90sec回収_前半",
    "90sec回収_後半",
    "180sec回収_前半",
    "180sec回収_後半",
    "240sec回収_前半",
    "240sec回収_後半",
    # wash
    "EtOHwash1_LS#4#1",
]
protocols = list(
    dict.fromkeys(sum([model.expand_string(pp) for pp in protocol_patterns], []))
)


class CellCultureMaholoModel(model.ProtocolModel):
    base_path: str = "C:\\BioApl\\DataSet\\proteo-03\\Protocol\\"
    protocol_list: list[str] = protocols

    @property
    def protocols(self) -> list[str]:
        return [self.base_path + p for p in self.protocol_list]

    async def hook(self, status: schemas.BioPortalStatus) -> None:
        print("[model] show_status: " + status.exp_status)
        if status.exp_status == "running":
            protocol: str = status.protocol
            print("[model] running: " + protocol)
            await asyncio.sleep(WAIT_TIME)
            if "getimage" in protocol:
                self.save_image()

    def save_image(self) -> None:
        print("[model] save image")
        now = datetime.now()
        filepath = nikon.get_filepath(now, "A", 1, path=IMAGE_DIR)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        print(f"[model] filepth: {filepath}")
        imwrite(str(filepath), image)


server.set_protocol_model(CellCultureMaholoModel())
uvicorn.run(server.app, host="localhost", port=63001)
