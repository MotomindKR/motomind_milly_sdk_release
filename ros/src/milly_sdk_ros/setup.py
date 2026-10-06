from setuptools import find_packages, setup

setup(
    name="milly_sdk_ros", version="1.0.0", packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/milly_sdk_ros"]),
        ("share/milly_sdk_ros", ["package.xml"]),
    ],
    install_requires=["setuptools"], zip_safe=True,
    entry_points={"console_scripts": [
        "driver = milly_sdk_ros.node:main",
        "discover = milly_sdk_ros.discover:main",
        "description_monitor = milly_sdk_ros.description_monitor:main",
    ]},
)
