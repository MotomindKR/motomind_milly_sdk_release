#!/usr/bin/env bash
# Source this file; never starts a node, modifies CAN or enables a motor.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'Use: source scripts/ros_env.sh' >&2
  exit 2
fi
_milly_ros_environment() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || return
  [[ -f /opt/ros/humble/setup.bash ]] || { echo 'ROS2 Humble is missing.' >&2; return 1; }
  [[ -f "$root/.venv_ros/bin/activate" ]] || { echo 'Run bash scripts/setup_ros_humble.sh first.' >&2; return 1; }
  [[ -f "$root/install/local_setup.bash" ]] || { echo 'Milly ROS build is missing. Run bash scripts/setup_ros_humble.sh.' >&2; return 1; }
  "$root/.venv_ros/bin/python" -s -c 'import sys; assert sys.version_info[:2] == (3, 10)' || return
  [[ -z "${ROS_DISTRO:-}" || "$ROS_DISTRO" == humble ]] || { echo 'Open a fresh terminal without another ROS distribution loaded.' >&2; return 1; }
  export MOTOMIND_CONFIG_DIR="$root/profiles"
  export PYTHONNOUSERSITE=1
  # Activation restores the pre-venv PATH; source ROS afterwards, also on repeat calls.
  source "$root/.venv_ros/bin/activate" || return
  source /opt/ros/humble/setup.bash || return
  source "$root/install/local_setup.bash" || return
  echo 'Milly ROS2 Humble environment ready (no node started).'
}
_milly_ros_environment
