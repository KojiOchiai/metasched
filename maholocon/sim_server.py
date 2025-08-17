import asyncio
from datetime import datetime
from pathlib import Path

import uvicorn
from cv2 import imwrite

from maholocon.maholo_api import model, schemas, server
from maholocon.maholo_api.microscope import nikon

WAIT_TIME = 1

IMAGE_DIR = Path("./nikon_save")
image = nikon.get_image(0.5)

IMAGE_DIR.mkdir(parents=True, exist_ok=True)


protocol_patterns = [
    # setup
    "move_plate6well_LS#9#LifterPlate#1_Co2IB#{1..2}#{1..20}",
    # loading/cleanup
    "move_plate6well_Co2IB#{1..2}#{1..20}_LS#{9..10}#LifterPlate#1",
    "move_plate6well_LS#{9..10}#LifterPlate#1_Co2IB#{1..2}#{1..20}",
    "move_plate6well_LS#9#LifterPlate#1_Dustbox#1",
    "move_plate6well_LS#9#LifterPlate#1_LS#{13..24}#LifterPlate#1",
    "move_tube50ml_CoolIB#{1..18}_AB#{1..3}",
    "move_tube50ml_CoolIB#{1..18}_LS#1#LifterTube50ml#1",
    "move_tube50ml_LS#{2..3}#LifterTube50ml#{1..3}_AB#4",
    "move_tube50ml_LS#{5..6}#LifterTube50ml#{1..3}_AB#4",
    "move_tube50ml_LS#1#LifterTube50ml#1_LS#2#LifterTube50ml#{1..3}",
    "move_tube50ml_LS#2#LifterTube50ml#{1..3}_LS#1#LifterTube50ml#1",
    "move_tube50ml_LS#4#LifterTube50ml#{1..3}_LS#1#LifterTube50ml#1",
    "move_tube50ml_LS#1#LifterTube50ml#1_LS#4#LifterTube50ml#{1..3}",
    "move_tube50ml_AB#{1..3}_CoolIB#{1..18}",
    "move_tube50ml_LS#1#LifterTube50ml#1_CoolIB#{1..18}",
    "move_tube50ml_AB#4_Dustbox#1",
    "move_tube50ml_AB#4_LS#{2..3}#LifterTube50ml#{1..3}",
    "move_tube50ml_AB#4_LS#{5..6}#LifterTube50ml#{1..3}",
    "move_tube1.5ml_LS#12#LifterTube1.5ml#{1..10}_LS#11#LifterTube1.5ml#1",
    "move_tube1.5ml_LS#11#LifterTube1.5ml#1_Dustbox#1",
    # protocols
    "getimage",
    "platecoating",
    "mediumchange",
    "sampling",
    "ethanolwash",
    "passage_253g1",
    "passage_hek293a",
]
protocols = list(
    dict.fromkeys(sum([model.expand_string(pp) for pp in protocol_patterns], []))
)
with open("protocols_sim.txt", "w") as f:
    f.write("\n".join(protocols))


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
