"""Per-launch RViz frame settings; never modify the installed template."""
from pathlib import Path
import re
import tempfile
import xml.etree.ElementTree as ET

import yaml


def style_robot_description(description):
    """RViz-only material overlay; keep the calibrated/model URDF unchanged.

    Each CAD link is one mesh, so this is a link palette, not a segmentation
    of real motor housings and covers. Geometry/dynamics are never modified.
    """
    root = ET.fromstring(description)
    for link in root.findall("link"):
        silver = link.get("name") in {"base_link", "finger_1", "finger_2"}
        material_name = "milly_silver" if silver else "milly_off_white"
        rgba = "0.65 0.68 0.72 1.0" if silver else "0.88 0.88 0.85 1.0"
        for visual in link.findall("visual"):
            for material in visual.findall("material"):
                visual.remove(material)
            material = ET.SubElement(visual, "material", name=material_name)
            ET.SubElement(material, "color", rgba=rgba)
    return ET.tostring(root, encoding="unicode")


def make_rviz_config(template, product_id):
    if not re.fullmatch(r"MILLY_[A-Za-z0-9]{1,10}", product_id):
        raise ValueError("invalid Milly product ID")
    config = yaml.safe_load(Path(template).read_text())
    manager = config["Visualization Manager"]
    manager["Global Options"]["Fixed Frame"] = product_id + "/base_link"
    for display in manager["Displays"]:
        if display.get("Class") == "rviz_default_plugins/RobotModel":
            display["TF Prefix"] = product_id
    directory = tempfile.TemporaryDirectory(prefix="milly-rviz-")
    path = Path(directory.name) / "milly.rviz"
    try:
        path.write_text(yaml.safe_dump(config, sort_keys=False))
    except BaseException:
        directory.cleanup()
        raise
    return directory, str(path)
