#!/usr/bin/env bash
# Install SDK wheels, build ROS sources and run import/model checks. Never opens CAN.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=false
case "${1:-}" in
  --dry-run) DRY_RUN=true ;;
  --help) echo 'Usage: bash scripts/setup_ros_humble.sh [--dry-run]'; echo 'Requires Ubuntu 22.04 x86_64 and an installed ROS2 Humble environment.'; exit 0 ;;
  '') ;;
  *) echo 'Unknown argument. Use --help.' >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || exit 2
[[ "$(uname -m)" == x86_64 ]] || { echo 'Requires x86_64.' >&2; exit 1; }
[[ -f /opt/ros/humble/setup.bash ]] || { echo 'Install ROS2 Humble on Ubuntu 22.04 first; see SDK_ROS2_guide.md.' >&2; exit 1; }
/usr/bin/python3 -c 'import sys; assert sys.version_info[:2] == (3, 10), "Requires system Python 3.10"'
grep -q 'VERSION_ID="22.04"' /etc/os-release || { echo 'Requires Ubuntu 22.04.' >&2; exit 1; }
export PYTHONNOUSERSITE=1
run() {
  if "$DRY_RUN"; then printf '[dry-run]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}
[[ -f "$ROOT/ros/src/milly_sdk_ros/package.xml" ]] || { echo 'ROS sources missing; use the complete release bundle.' >&2; exit 1; }
run sudo apt-get install -y build-essential cmake python3-venv python3-pip python3-yaml python3-tk \
  python3-colcon-common-extensions libusb-1.0-0 ros-humble-ros-base \
  ros-humble-robot-state-publisher ros-humble-rviz2
run /usr/bin/python3 "$ROOT/scripts/ci/verify_release.py"
if [[ ! -f "$ROOT/.venv_ros/bin/python" ]]; then
  run /usr/bin/python3 -m venv --system-site-packages "$ROOT/.venv_ros"
else
  "$ROOT/.venv_ros/bin/python" -c 'import sys; assert sys.version_info[:2] == (3,10) and sys.base_prefix == "/usr", "Existing .venv_ros must use system Python 3.10"'
  grep -q 'include-system-site-packages = true' "$ROOT/.venv_ros/pyvenv.cfg" || { echo 'Existing .venv_ros must include ROS system packages. Rename it, then rerun installation.' >&2; exit 1; }
fi
run "$ROOT/.venv_ros/bin/python" "$ROOT/scripts/ci/install_wheels.py"
run "$ROOT/.venv_ros/bin/python" -m pip check
# Run colcon with the same interpreter as the installed SDK and generated ROS bindings.
run bash -c 'source /opt/ros/humble/setup.bash && cd "$1" && exec "$1/.venv_ros/bin/python" -m colcon build --base-paths ros/src --cmake-args -DCMAKE_BUILD_TYPE=Release -DPython3_EXECUTABLE="$1/.venv_ros/bin/python" -DPYTHON_EXECUTABLE="$1/.venv_ros/bin/python"' _ "$ROOT"
if ! "$DRY_RUN"; then
  # ROS setup scripts do not support nounset.
  set +u
  source "$ROOT/scripts/ros_env.sh"
  python "$ROOT/scripts/check_ros_install.py"
  echo 'Installation verified (no CAN). New terminal: source scripts/ros_env.sh'
fi
