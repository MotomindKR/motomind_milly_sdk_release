from pathlib import Path
import xml.etree.ElementTree as ET

import yaml

from milly_sdk_ros.rviz_config import make_rviz_config, style_robot_description


def test_per_robot_frames_do_not_modify_template():
    sdk = next(parent for parent in Path(__file__).resolve().parents if (parent/'ros/src').is_dir())
    template = sdk / "ros/src/milly_sdk_description/rviz/milly.rviz"
    original = template.read_bytes()
    outputs = []
    try:
        for product in ("MILLY_8H2D", "MILLY_TEST"):
            directory, path = make_rviz_config(template, product)
            outputs.append((directory, path))
            config = yaml.safe_load(Path(path).read_text())
            manager = config["Visualization Manager"]
            assert manager["Tools"] == [{"Class": "rviz_default_plugins/MoveCamera"}]
            assert manager["Views"]["Current"]["Class"] == "rviz_default_plugins/Orbit"
            assert manager["Global Options"]["Fixed Frame"] == product + "/base_link"
            robot = next(d for d in manager["Displays"] if d["Class"] == "rviz_default_plugins/RobotModel")
            assert robot["TF Prefix"] == product
            assert robot["Description Topic"]["Value"] == "robot_description"
            robot.pop("TF Prefix")
            manager["Global Options"]["Fixed Frame"] = "base_link"
            assert config == yaml.safe_load(original)
        assert outputs[0][1] != outputs[1][1]
        assert template.read_bytes() == original
    finally:
        for directory, path in outputs:
            directory.cleanup()
            assert not Path(path).exists()


def test_visual_palette_changes_only_visual_materials():
    original = '''<robot name="milly">
      <link name="base_link"><visual><geometry><mesh filename="base.stl"/></geometry></visual></link>
      <link name="link_1">
        <inertial><mass value="1.2"/></inertial>
        <visual><origin xyz="0 0 1"/><geometry><mesh filename="arm.stl" scale="0.001 0.001 0.001"/></geometry><material name="old"><color rgba="1 0 0 1"/></material></visual>
        <collision><geometry><mesh filename="arm.stl"/></geometry></collision>
      </link>
      <link name="finger_1"><visual><geometry><box size="1 2 3"/></geometry></visual></link>
      <link name="finger_2"><visual><geometry><box size="1 2 3"/></geometry></visual></link>
      <joint name="joint_1" type="revolute"><parent link="base_link"/><child link="link_1"/><axis xyz="0 0 1"/><limit lower="-2.62" upper="2.62" effort="50" velocity="5"/></joint>
    </robot>'''
    before = ET.fromstring(original)
    result = style_robot_description(original)
    after = ET.fromstring(result)
    assert style_robot_description(result) == result
    for link in after.findall("link"):
        material = link.find("visual/material")
        assert len(link.findall("visual/material")) == 1
        expected = "0.88 0.88 0.85 1.0" if link.get("name") == "link_1" else "0.65 0.68 0.72 1.0"
        assert material.find("color").get("rgba") == expected
        assert material.get("name") == ("milly_off_white" if link.get("name") == "link_1" else "milly_silver")
    for root in (before, after):
        for visual in root.findall("link/visual"):
            for material in visual.findall("material"):
                visual.remove(material)
    assert ET.tostring(before) == ET.tostring(after)
