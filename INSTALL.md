# Install — Motomind Milly SDK

Linux and Windows install differently — follow the section for your OS.

---

## Linux (x86_64) — fully supported

### 1. Prerequisites
- Linux with SocketCAN (Jetson, or a PC with a CAN interface).
- Python **3.10, 3.11, or 3.12**.
- Bring the USB-to-CAN adapter up as a CAN interface (bitrate must match the motors):
  ```bash
  sudo ip link set can0 up type can bitrate 1000000
  ```

### 2. Install
Wheels are provided per Python version under `dist/linux_x86_64/`
(`python3.10` / `python3.11` / `python3.12`). Install from the folder that
matches your Python:

```bash
python3 --version                                    # e.g. Python 3.11.x
python3 -m venv .venv && source .venv/bin/activate   # optional (or use your own env)
python -m pip install --upgrade pip
python -m pip install dist/linux_x86_64/python3.11/*.whl   # <-- your version's folder
```

This installs both wheels — `motomind_milly_sdk` (discovery, motion, gripper,
safety) and `motomind_robot_model` (gravity comp, FK, IK) — plus Pinocchio and
NumPy from PyPI. No separate step for gravity comp.

### 3. Verify
```bash
motomind-milly-robots          # lists connected robots by product ID (on can0)
python -c "import motomind_milly as mm; print(mm.__version__)"
```
Then follow the Quick start in [README.md](README.md) and the full
[SDK_guide_user.md](SDK_guide_user.md).

---

## Windows — not in this release yet

There is **no Windows wheel** in this bundle. Motor control is compiled against
Linux SocketCAN, and the Windows path (robot discovery + control over a USB-CAN
gs_usb adapter) still needs the core to build and be verified on Windows.

When it is ready, Windows wheels will ship under `dist/windows/python3.X/` and
this section will carry the steps. For now, run the SDK on the **Linux** machine
that talks to the arm.

---

## Register your robot (tuning profile)

Each robot is opened by the product ID engraved on it (e.g. `MILLY_ABCD`). The
SDK ships canonical + default tuning inside the wheel; to customise one robot,
drop a `<PRODUCT_ID>.yaml` with only the keys you want to change into your config
dir (set `MOTOMIND_CONFIG_DIR` to it, or use the packaged `profiles/` dir). See
`SDK_guide_user.md` §2 and the bundled `profiles/` (SAMPLE + DEFAULT).
