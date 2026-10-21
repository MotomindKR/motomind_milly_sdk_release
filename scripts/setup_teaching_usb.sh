#!/usr/bin/env bash
# Install the tested FTDI latency rule. Never opens a serial port or triggers devices.
set -euo pipefail

usage() {
  echo 'Usage: bash scripts/setup_teaching_usb.sh [--port /dev/ttyACM0] [--dry-run]'
  echo 'Install the 1 ms USB latency rule for FTDI adapters with USB ID 0403:6014.'
  echo 'ttyACM ports do not use this FTDI setting; no rule is installed for them.'
  echo 'Run once on each Linux host; sudo is requested when installing.'
}

DRY_RUN=false
TEACHING_PORT='/dev/ttyACM0'
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --port)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      TEACHING_PORT="$2"; shift 2 ;;
    --help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
[[ "$TEACHING_PORT" =~ ^/dev/tty(USB|ACM)[0-9]+$ ]] || { echo 'Expected /dev/ttyUSB<number> or /dev/ttyACM<number>.' >&2; exit 2; }
[[ "$(uname -s)" == Linux ]] || { echo 'Requires Linux with udev.' >&2; exit 1; }
if [[ "$TEACHING_PORT" == /dev/ttyACM* ]]; then
  echo "$TEACHING_PORT: FTDI latency_timer setting does not apply; no system changes."
  echo "Check permissions, then use --port $TEACHING_PORT with the teaching examples."
  exit 0
fi
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
echo "Check: cat /sys/bus/usb-serial/devices/${TEACHING_PORT##*/}/latency_timer (expected: 1)"
