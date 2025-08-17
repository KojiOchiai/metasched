import pathlib
import shutil

"""
sample choices:
- CO2 incubator(6well microplate)-1 #1
- Lifter-stocker(6well microplate)-9 #1
- Lifter-stocker(1.5ml tube)-12 #1
- Alumibath-non cover(50ml tube)-1 #1
- Cool-incubator(50ml tube)-1 #1
- Lifter-stocker(50ml tube)-1
- Lifter-stocker(1.5ml tube)-12 #1
"""

"""
lifter choices:
<settingParam8 name="Stocker #8">無し</settingParam8>
<settingParam9 name="Stocker #9">Plate(6Well)</settingParam9>
"""

device_dict = {
    "Co2IB": "CO2 incubator({labware})-{section} #{jig}",
    "CoolIB": "Cool-incubator({labware})-{section} #{jig}",
    "AB": "Alumibath-non cover({labware})-{section} #{jig}",
    "LS": "Lifter-stocker({labware})-{section} #{jig}",
    "Lifter": "Lifter-stocker({labware})-{section}",
}

labware_dict = {
    "plate6well": "6well microplate",
    "tube50ml": "50ml tube",
    "tube1.5ml": "1.5ml tube",
}


class LifterInit:
    labware_dict = {
        "plate6well": "Plate(6Well)",
        "tube50ml": "Tube(50ml)",
        "tube1.5ml": "Tube(1.5ml)",
    }

    def __init__(self, labware: str, section: int):
        self.labware = labware
        self.section = section

    def xml_text(self):
        start_tag = f'<settingParam{self.section} name="Stocker #{self.section}">'
        end_tag = f"</settingParam{self.section}>"
        inner_text = "無し"
        if self.labware in self.labware_dict:
            inner_text = self.labware_dict[self.labware]
        return f"{start_tag}{inner_text}{end_tag}"


class Position:
    device: str
    section: int
    jig: int

    def __init__(self, device_str: str):
        device, section, jig = self.parse_device(device_str)
        self.device = device
        self.section = section
        self.jig = jig

    def parse_device(self, device: str):
        """
        input string like 'Co2IB#1#2' and return tuple ('Co2IB', 1, 2)
        """
        tokens = device.split("#")
        device = tokens[0]
        if device not in device_dict:
            raise ValueError(f"Invalid device: {device}")
        if device == "Co2IB":
            return device, tokens[1], tokens[2]
        elif device == "AB" or device == "CoolIB":
            return device, "1", tokens[1]
        elif device == "LS":
            return device, tokens[1], tokens[3]

    def xml_text(self, labware: str):
        template = device_dict[self.device]
        return template.format(labware=labware, section=self.section, jig=self.jig)


class MoveProtocol:
    def __init__(self, protocol_name: str):
        _, labware, from_, to_ = protocol_name.split("_")
        self.protocol_name = protocol_name
        self.labware = labware
        self.from_device = Position(from_)
        if self.from_device.device not in device_dict:
            raise ValueError(f"Invalid device: {from_}")
        self.to_device = Position(to_)
        if self.to_device.device not in device_dict:
            raise ValueError(f"Invalid device: {to_}")

    def match(self, protocol: "MoveProtocol"):
        if self.from_device.device == "LS" and self.to_device.device == "LS":
            if self.from_device.section == self.to_device.section:
                return (
                    self.labware == protocol.labware
                    and self.from_device.device == protocol.from_device.device
                    and self.to_device.device == protocol.to_device.device
                    and protocol.from_device.section == protocol.to_device.section
                )
            else:
                return (
                    self.labware == protocol.labware
                    and self.from_device.device == protocol.from_device.device
                    and self.to_device.device == protocol.to_device.device
                    and protocol.from_device.section != protocol.to_device.section
                )
        return (
            self.labware == protocol.labware
            and self.from_device.device == protocol.from_device.device
            and self.to_device.device == protocol.to_device.device
        )

    def surround_with_arrows(self, text: str) -> str:
        return f">{text}<"

    @property
    def lifter_xml(self):
        template = device_dict["Lifter"]
        labware = labware_dict[self.labware]
        return self.surround_with_arrows(
            template.format(labware=labware, section=self.to_device.section)
        )

    @property
    def from_xml(self):
        template = device_dict[self.from_device.device]
        labware = labware_dict[self.labware]
        return self.surround_with_arrows(
            template.format(
                labware=labware,
                section=self.from_device.section,
                jig=self.from_device.jig,
            )
        )

    @property
    def to_xml(self):
        template = device_dict[self.to_device.device]
        labware = labware_dict[self.labware]
        return self.surround_with_arrows(
            template.format(
                labware=labware, section=self.to_device.section, jig=self.to_device.jig
            )
        )

    @property
    def from_lifter_xml(self):
        return LifterInit(self.labware, self.from_device.section).xml_text()

    @property
    def to_lifter_xml(self):
        return LifterInit(self.labware, self.to_device.section).xml_text()

    def remove_lifters(self, xml: str):
        empty_lifter_xml = LifterInit("", self.from_device.section).xml_text()
        xml = xml.replace(self.from_lifter_xml, empty_lifter_xml)
        empty_lifter_xml = LifterInit("", self.to_device.section).xml_text()
        xml = xml.replace(self.to_lifter_xml, empty_lifter_xml)
        return xml

    def add_lifters(self, xml: str):
        empty_lifter_xml = LifterInit("", self.from_device.section).xml_text()
        xml = xml.replace(empty_lifter_xml, self.from_lifter_xml)
        empty_lifter_xml = LifterInit("", self.to_device.section).xml_text()
        xml = xml.replace(empty_lifter_xml, self.to_lifter_xml)
        return xml


class MoveProtocolTemplates:
    def __init__(self):
        current_dir = pathlib.Path(__file__).parent
        self.template_dir = current_dir / "move_protocol_templates"
        protocol_templates = self.template_dir.glob("move_*")
        self.templates = [
            MoveProtocol(template.name) for template in protocol_templates
        ]

    def choice_template(self, protocol: MoveProtocol):
        for template in self.templates:
            if template.match(protocol):
                return template
        raise ValueError(f"No template found for {protocol}")


class MoveProtocolGenerator:
    def __init__(self, project_name: str):
        self.project_name = pathlib.Path(project_name)
        self.make_project_directory()

    def make_project_directory(self):
        self.project_name.mkdir(exist_ok=True)

    def generate(self, protocol_name: str):
        protocol = MoveProtocol(protocol_name)
        # make protocol directory
        templates = MoveProtocolTemplates()
        template = templates.choice_template(protocol)
        shutil.rmtree(self.project_name / protocol.protocol_name, ignore_errors=True)
        shutil.copytree(
            templates.template_dir / template.protocol_name,
            self.project_name / protocol.protocol_name,
        )

        # edit PROJECT.PRJ
        with open(self.project_name / protocol_name / "PROJECT.PRJ", "r") as f:
            xml = f.read()
        xml = xml.replace(template.from_xml, "###from###")
        xml = xml.replace(template.to_xml, "###to###")
        xml = xml.replace("###from###", protocol.from_xml)
        xml = xml.replace("###to###", protocol.to_xml)
        xml = xml.replace(template.lifter_xml, "###lifter###")
        xml = xml.replace("###lifter###", protocol.lifter_xml)
        xml = template.remove_lifters(xml)
        xml = protocol.add_lifters(xml)
        with open(self.project_name / protocol_name / "PROJECT.PRJ", "w") as f:
            f.write(xml)
