# Examples

Run the CAN setup and robot discovery before using a motion example:

```bash
bash scripts/set_can_interface.sh
python examples/discover_robots.py
```

`discover_robots.py` does not move any motors. Use the engraved product ID it
prints (for example `MILLY_ABCD`) with every other arm-control example.

> Keep clear of the arm before confirming a move. End every example with
> `Ctrl-C`: it calls `shutdown()` and engages the damping latch. Do not use
> `disable()` as a normal program exit because it removes torque immediately.

## Available examples

| Example | What it does |
| --- | --- |
| `discover_robots.py` | Finds connected product IDs without touching the motors. |
| `motor_state_check.py` | Read-only motor feedback check by default. `--move` enables a gentle diagnostic motion. |
| `move_j_test.py` | Plans a joint-space move of all six arm joints to 0 rad, then closes the gripper. |
| `move_p_test.py` | Plans a Cartesian move to the flange pose of the all-zero joint posture, then closes the gripper. |
| `move_mit_test.py` | Demonstrates a three-second MIT warm start of all joints and the gripper to 0 rad. |
| `gravity_float.py` | Enables factory-calibrated gravity compensation for hand-guiding. |
| `gripper_test.py` | Interactive gripper open, close, position, and gain check. |
| `button_test.py` | Read-only button/LED-board communication and reliability check. |

## Commands

```bash
# Read feedback only; add --move only for the gentle motion diagnostic.
python examples/motor_state_check.py --product-id MILLY_ABCD

# The following examples open the motor-state GUI by default.
python examples/move_j_test.py --product-id MILLY_ABCD
python examples/move_p_test.py --product-id MILLY_ABCD
python examples/move_mit_test.py --product-id MILLY_ABCD
python examples/gravity_float.py --product-id MILLY_ABCD

# Interactive gripper test.
python examples/gripper_test.py --product-id MILLY_ABCD
```

Pass `--gui=false` to the motion and gravity examples when a GUI is not wanted.
For API details, limits, collision preflight, and tuning profiles, see the
[SDK user guide](../SDK_guide_user.md).
