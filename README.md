# Motomind Milly SDK

Python SDK for the **Milly** 6-DOF robot arm (+ gripper), built on Robstride CAN
motors. Discover a robot by its engraved product ID, then move it, hold it,
gravity-compensate (drag/teach), and drive the gripper — all through one Python
API over a frozen, safety-checked C++ core.

> **MIT licensed** — see [LICENSE](LICENSE). Free to use, modify, and redistribute.

## Install

See [INSTALL.md](INSTALL.md) (Linux 22.04+ (x86_64); Windows not yet). Wheels are per Python version (3.10 / 3.11 / 3.12):

```bash
python -m pip install dist/linux_x86_64/python3.X/*.whl   # <- your Python version (SDK + robot model)
```

## CAN interface setup (Linux)

Before robot discovery or control, configure the `can0` USB-CAN interface with
the supplied script. It sets the queue length and Milly's required 1 Mbps
bitrate, then brings the interface up.

```bash
bash scripts/set_can_interface.sh
```

The script uses `sudo` and briefly takes `can0` down, so never run it while the
robot is being controlled.

## Milly joint limits

These are fixed canonical limits; the per-robot tuning file cannot change them.
`position` is the MIT command range (the SDK clamps a direct `move_mit` command
to it). `safe position` is the wider measured-position safety envelope: leaving
it faults the arm and starts the damping latch.

| Joint (motor ID) | Position [rad] | Safe position [rad] | MIT kp | MIT kd |
| --- | ---: | ---: | ---: | ---: |
| joint_1 (1) | -2.62 .. 2.62 | -2.72 .. 2.72 | 0 .. 200 | 0 .. 20 |
| joint_2 (2) | 0.00 .. 3.14 | -0.10 .. 3.24 | 0 .. 200 | 0 .. 20 |
| joint_3 (3) | 0.00 .. 2.97 | -0.10 .. 3.07 | 0 .. 200 | 0 .. 20 |
| joint_4 (4) | -2.00 .. 2.00 | -2.15 .. 2.15 | 0 .. 100 | 0 .. 10 |
| joint_5 (5) | -1.72 .. 1.77 | -1.87 .. 1.92 | 0 .. 100 | 0 .. 10 |
| joint_6 (6) | -1.50 .. 1.50 | -1.60 .. 1.60 | 0 .. 100 | 0 .. 10 |
| gripper (7) | -2.30 .. 0.00 | -2.40 .. 0.10 | 0 .. 50 | 0 .. 5 |

All motors also have velocity limits of -20 .. 20 rad/s and torque limits of
-30 .. 30 Nm. User-editable profile gains use these same canonical, per-joint
limits; the `motion` arrays are ordered joint_1 through joint_6 (base → wrist).

## Self-collision preflight

`move_j` and `move_p` check the entire planned joint path against the exact
collision meshes before sending a command. A newly predicted self-collision
raises an error and leaves the current supervisor mode unchanged. The bundled
`milly_description/` directory is found automatically when running from the
release folder or one of its subdirectories. For another location, set
`MOTOMIND_MILLY_DESCRIPTION_DIR` to the `milly_description` directory.

## Quick start

```python
import time
import motomind_milly as mm
from motomind_milly.monitor import MotorMonitor

mm.enable_logging()

arm = mm.create_arm("MILLY_ABCD")   # discover + verify + connect (by product ID)
arm.set_max_vel(0.3)
# Start the GUI before enable(): it uses the same Arm/manager (no second CAN owner).
MotorMonitor(arm.manager, arm._config, poll_ms=250).start()
time.sleep(1.0)
arm.enable()                         # motors on, holds its pose (supervisor auto-starts)

try:
    arm.move_j([0.0, 0.0, 0.0, 0.0, 0.0, 0.0], max_vel=0.2)  # joint move (rad)
    grip = arm.init_effector()        # gripper
    grip.open()
    time.sleep(0.5) 
    grip.close()
    print("motion complete; press Ctrl-C to shut down safely")
    while True:
        time.sleep(0.2)
except KeyboardInterrupt:
    print("shutting down with damping latch")
finally:
    arm.shutdown()                    # safe exit (damping latch — does NOT drop)
```

- Find connected robots: `motomind-milly-robots`
- The embedded GUI shows motor state and provides an E-STOP; closing its window
  only closes the GUI. End the program with `arm.shutdown()`.

## Docs & examples

- **[SDK_guide_user.md](SDK_guide_user.md)** — full API guide (motion, gravity
  comp, gripper, safety, button, profiles).
- **[examples/](examples/)** — runnable: `discover_robots.py` (find your robot),
  `motor_state_check.py`, `move_j_test.py`, `move_p_test.py`, `move_mit_test.py`,
  `gravity_float.py` (drag/teach), `gripper_test.py`, `button_test.py`.

## Platforms

Linux (SocketCAN) is supported today. Windows (gs_usb / USB-CAN) is in progress.

## Contact

For further questions, feel free to contact us.
- https://www.motomind.co.kr/ko
- contact@motomind.co.kr