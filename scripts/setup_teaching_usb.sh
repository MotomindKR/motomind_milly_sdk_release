#!/usr/bin/env bash
# Install the tested FTDI latency rule. Never opens a serial port or triggers devices.
set -euo pipefail

usage() {
  echo 'Usage: bash scripts/setup_teaching_usb.sh [--dry-run]'
  echo 'Install the 1 ms USB latency rule for FTDI adapters with USB ID 0403:6014.'
  echo 'Run once on each Linux host; sudo is requested when installing.'
}

DRY_RUN=false
case "${1:-}" in
  --dry-run) DRY_RUN=true ;;
  --help) usage; exit 0 ;;
  '') ;;
  *) usage >&2; exit 2 ;;
esac
[[ $# -le 1 ]] || { usage >&2; exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo 'Requires Linux with udev.' >&2; exit 1; }
command -v udevadm >/dev/null || { echo 'udevadm is missing; install udev first.' >&2; exit 1; }

RULE_PATH='/etc/udev/rules.d/99-milly-teaching-latency.rules'
RULE_FILE="$(mktemp)"
trap 'rm -f "$RULE_FILE"' EXIT
cat > "$RULE_FILE" <<'EOF'
ACTION=="add", SUBSYSTEM=="usb-serial", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6014", ATTR{latency_timer}="1"
EOF

run() {
  if "$DRY_RUN"; then
    printf '[dry-run]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

cat "$RULE_FILE"
run sudo install -m 0644 "$RULE_FILE" "$RULE_PATH"
run sudo udevadm control --reload-rules
if ! "$DRY_RUN"; then
  echo "Installed: $RULE_PATH"
fi
echo 'Stop the teaching program, then disconnect and reconnect the USB adapter.'
echo 'Check: cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer (expected: 1)'
