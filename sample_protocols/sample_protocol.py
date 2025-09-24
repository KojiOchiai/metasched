from datetime import datetime, timedelta

from src.protocol import (
    ExistingLabware,
    ExistingLabwareSetup,
    Label,
    LabelStorage,
    Loading,
    NewLabware,
    Protocol,
    Reagent,
    RequirementSetup,
    Store,
    StoreType,
    Unloading,
)

liquid_name_storage = LabelStorage()
liquid_name_storage.add_label("PBS", aliases=["Phosphate Buffered Saline"])
liquid_name_storage.add_label("DMEM", aliases=["Dulbecco's Modified Eagle Medium"])
liquid_name_storage.add_label("medium", aliases=["cell culture medium"])

labware_name_storage = LabelStorage()
labware_name_storage.add_label("tube_50ml")
labware_name_storage.add_label("tube_15ml", aliases=["15ml conical tube"])
labware_name_storage.add_label("tube_1.5ml", aliases=["1.5ml microcentrifuge tube"])
labware_name_storage.add_label("well_plate_6", aliases=["6-well plate"])

loading = Loading(
    labware=NewLabware(labware_type="tube_rack_15_50ml"), store_condition="cold_4"
)
getimage = Protocol(
    protocol_name="getimage",
    duration=timedelta(minutes=30),
    existing_labwares={
        "input_plate": ExistingLabwareSetup(
            requirement=ExistingLabware(labware_type="well_plate_6"),
            prepare_to="microscope/1",
        )
    },
)
store = Store(store_condition="cold_4", optimal_time=timedelta(hours=2))
