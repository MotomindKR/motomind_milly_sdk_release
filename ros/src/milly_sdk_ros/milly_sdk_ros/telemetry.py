"""Pure conversions; never fabricate joint measurements or infer freshness from motion."""
import math


def joint_values(rows, gripper_range):
    names, positions, velocities = [], [], []
    for row in rows:
        if not row["fresh"]:
            continue
        name = row["joint_name"]
        if name == "gripper":
            # RAW rotary angle -> CAD finger travel is not calibrated yet.
            # Keep raw feedback in motor_states; do not invent finger positions.
            continue
        elif name in {f"joint_{i}" for i in range(1, 7)}:
            names.append(name)
            positions.append(row["position"])
            velocities.append(row["velocity"])
    return names, positions, velocities


def quaternion(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy,
            cr*cp*sy-sr*sp*cy, cr*cp*cy+sr*sp*sy)
