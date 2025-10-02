from src.experiment import Experiment
from src.labware import LabwareType


class Workspace:
    labware_types: dict[str, LabwareType]
    experiments: list[Experiment]

    def __init__(self, labware_types: list[LabwareType]) -> None:
        self.labware_types = {lt.name: lt for lt in labware_types}
        self.experiments = []
