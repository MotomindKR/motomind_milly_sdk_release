#!/usr/bin/env python3
"""Select a Linux USB camera and show its live video; no Milly/ROS connection.

  python camera_preview.py --list
  python camera_preview.py
  python camera_preview.py --device /dev/v4l/by-path/pci-...-video-index0

Only the selected camera streams. --help and --list need no OpenCV installation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import math
import os
from pathlib import Path
import shlex
import struct
import sys
import time


# Linux x86_64 V4L2 ABI: struct v4l2_capability, VIDIOC_QUERYCAP.
# https://docs.kernel.org/userspace-api/media/v4l/vidioc-querycap.html
CAPABILITY = struct.Struct("=16s32s32s6I")
VIDIOC_QUERYCAP = 0x80685600
V4L2_CAP_DEVICE_CAPS = 0x80000000
V4L2_CAP_VIDEO_CAPTURE = 0x00000001
V4L2_CAP_VIDEO_CAPTURE_MPLANE = 0x00001000


@dataclass(frozen=True)
class Camera:
    device: Path
    name: str
    bus: str
    by_id: Path | None = None
    by_path: Path | None = None
    manufacturer: str = ""
    product: str = ""
    usb_id: str = ""
    serial: str = ""
    duplicate_serial: bool = False

    @property
    def preferred_path(self) -> Path:
        # Supplied HBVCAM cameras share a factory serial: by-id can silently
        # switch to another unit. Prefer the physical USB port for all cameras.
        return self.by_path or self.device

    @property
    def gripper_candidate(self) -> bool:
        # Verified on the supplied HBVCAM camera. This identifies a model,
        # not a particular robot, left/right arm, or camera serial number.
        return self.usb_id == "0bdc:8088" and self.manufacturer == "HBVCAM Camera"


def read_text(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def usb_details(sys_device: Path) -> dict[str, str]:
    for parent in sys_device.resolve().parents:
        vendor, product = read_text(parent / "idVendor"), read_text(parent / "idProduct")
        if vendor and product:
            return dict(manufacturer=read_text(parent / "manufacturer"),
                        product=read_text(parent / "product"), usb_id=f"{vendor}:{product}",
                        serial=read_text(parent / "serial"))
    return {}


def aliases(directory: Path) -> dict[Path, Path]:
    result = {}
    for alias in sorted(directory.glob("*")):
        try:
            result.setdefault(alias.resolve(strict=True), alias)
        except OSError:
            continue
    return result


def query_capture(device: Path) -> tuple[str, str] | None:
    import fcntl

    buffer = bytearray(CAPABILITY.size)
    fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, VIDIOC_QUERYCAP, buffer)
    finally:
        os.close(fd)
    _, card, bus, _, capabilities, device_caps, *_ = CAPABILITY.unpack(buffer)
    caps = device_caps if capabilities & V4L2_CAP_DEVICE_CAPS else capabilities
    if not caps & (V4L2_CAP_VIDEO_CAPTURE | V4L2_CAP_VIDEO_CAPTURE_MPLANE):
        return None  # Metadata-only nodes are not image sources.
    decode = lambda value: value.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    return decode(card), decode(bus)


def discover_cameras(sys_class: Path = Path("/sys/class/video4linux"),
                     dev_root: Path = Path("/dev")) -> tuple[list[Camera], list[str]]:
    by_id = aliases(dev_root / "v4l/by-id")
    by_path = aliases(dev_root / "v4l/by-path")
    cameras, issues = [], []
    for entry in sorted(sys_class.glob("video*"), key=lambda p: int(p.name[5:])):
        device = dev_root / entry.name
        try:
            info = query_capture(device)
        except OSError as exc:
            issues.append(f"{device}: {exc.strerror or exc}")
            continue
        if info is not None:
            name, bus = info
            cameras.append(Camera(device, name, bus, by_id.get(device), by_path.get(device),
                                  **usb_details(entry / "device")))
    identities = {}
    for camera in cameras:
        if camera.usb_id and camera.serial:
            identities.setdefault((camera.usb_id, camera.serial), set()).add(camera.bus)
    cameras = [replace(c, duplicate_serial=len(identities.get((c.usb_id, c.serial), ())) > 1)
               for c in cameras]
    return cameras, issues


def print_cameras(cameras: list[Camera]) -> None:
    print("영상 입력 카메라 (목록 조회는 영상을 스트리밍하지 않습니다):")
    for index, camera in enumerate(cameras, 1):
        label = " [Milly 그리퍼 카메라 후보 — 납품 모델 USB 정보 일치]" if camera.gripper_candidate else ""
        print(f"  [{index}] {camera.name}{label}")
        print(f"      장치: {camera.device} | USB: {camera.usb_id or '-'} | 위치: {camera.bus}")
        if camera.manufacturer or camera.product or camera.serial:
            print(f"      제조사: {camera.manufacturer or '-'} | 모델: {camera.product or '-'}"
                  f" | 시리얼: {camera.serial or '-'}")
        if camera.duplicate_serial:
            print("      시리얼 중복: 같은 모델 여러 대가 같은 값을 사용합니다. by-path로 구분하세요.")
        if camera.by_id:
            suffix = " (시리얼 중복 — 개체 구분에 사용 불가)" if camera.duplicate_serial else ""
            print(f"      by-id: {camera.by_id}{suffix}")
        if camera.by_path:
            print(f"      by-path (권장): {camera.by_path}")
    if not cameras:
        print("  영상 입력 장치가 없습니다. USB 연결과 장치 접근 권한을 확인하세요.")


def select_camera(cameras: list[Camera], device: str | None) -> tuple[Camera, Path] | None:
    if device is not None:
        try:
            resolved = Path(device).resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(f"지정한 카메라 경로를 확인할 수 없습니다: {device}: {exc}") from exc
        for camera in cameras:
            if resolved == camera.device:
                if camera.duplicate_serial and Path(device).parent.name == "by-id":
                    raise RuntimeError("시리얼이 중복되어 by-id로 개체를 구분할 수 없습니다. --list의 by-path를 지정하세요.")
                return camera, Path(device)
        raise RuntimeError(f"영상 입력 카메라가 아닙니다: {device}. --list로 이름과 권한을 확인하세요.")
    if not cameras:
        raise RuntimeError("사용할 카메라가 없습니다. USB 연결과 /dev/video* 접근 권한을 확인하세요.")
    print("HBVCAM Camera / USB 0bdc:8088가 납품 모델 후보입니다. 영상으로 확인하세요.")
    while True:
        try:
            answer = input("카메라 번호 선택 (q: 종료): ").strip()
        except EOFError as exc:
            raise RuntimeError("선택 입력이 없습니다. 터미널에서 실행하거나 --device 경로를 지정하세요.") from exc
        if answer.lower() == "q":
            return None
        if answer.isascii() and answer.isdecimal() and 1 <= int(answer) <= len(cameras):
            camera = cameras[int(answer) - 1]
            return camera, camera.preferred_path
        print(f"1~{len(cameras)} 중 하나를 입력하세요. Enter만으로는 선택하지 않습니다.")


def preview(camera: Camera, device: Path, args: argparse.Namespace) -> None:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise RuntimeError("영상 창을 열 수 없습니다. 데스크톱 터미널에서 실행하세요 (--list는 창 없이 가능).")
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV가 필요합니다: python -m pip install 'opencv-python>=4.8,<5'") from exc
    if "NONE" in next((line for line in cv2.getBuildInformation().splitlines()
                            if line.strip().startswith("GUI:")), ""):
        raise RuntimeError("GUI 없는 OpenCV입니다. opencv-python-headless 대신 opencv-python을 설치하세요.")

    title = f"Milly USB camera | {camera.device.name} | q / Esc: quit"
    capture = cv2.VideoCapture()
    window_created = False
    try:
        if not capture.open(str(device), cv2.CAP_V4L2):
            raise RuntimeError(f"카메라를 열 수 없습니다: {device}. 다른 앱의 사용 여부·USB 연결·권한을 확인하세요.")
        # The supplied camera uses MJPG. Drivers may negotiate different values;
        # always report the actual frame size and driver-reported FPS below.
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        capture.set(cv2.CAP_PROP_FPS, args.fps)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError("첫 영상을 읽지 못했습니다. 카메라 사용 중인 앱·케이블·지원 해상도를 확인하세요.")
        print(f"영상: {frame.shape[1]}x{frame.shape[0]}, 드라이버 FPS: {capture.get(cv2.CAP_PROP_FPS):g}")
        cv2.namedWindow(title, cv2.WINDOW_NORMAL)
        window_created = True
        cv2.resizeWindow(title, min(frame.shape[1], 1280), min(frame.shape[0], 720))
        print("종료: 영상 창에서 q / Esc, 창 닫기 또는 터미널 Ctrl+C.", flush=True)
        started = time.monotonic()
        while True:
            cv2.imshow(title, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
            try:
                visible = cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE)
            except cv2.error:
                # Qt removes its last window on close and raises instead of
                # returning 0 from this visibility query.
                break
            if visible < 1:
                break
            if args.duration is not None and time.monotonic() - started >= args.duration:
                break
            ok, frame = capture.read()
            if not ok or frame is None:
                raise RuntimeError("영상 수신이 중단되었습니다. USB 연결을 확인하고 다시 실행하세요.")
    except cv2.error as exc:
        raise RuntimeError(f"OpenCV 영상 표시 오류: {exc}") from exc
    finally:
        capture.release()
        if window_created:
            cv2.destroyAllWindows()


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("양의 정수가 필요합니다")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("유한한 양수가 필요합니다")
    return number


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="USB 카메라 선택 및 실시간 영상 (Linux, 로봇 연결 불필요)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="영상 입력 장치 정보만 조회 (OpenCV 불필요)")
    mode.add_argument("--device", metavar="PATH", help="--list에서 확인한 /dev/v4l/by-id, by-path 또는 /dev/videoN")
    parser.add_argument("--width", type=positive_int, default=1280, help="요청 영상 너비 (기본: 1280)")
    parser.add_argument("--height", type=positive_int, default=720, help="요청 영상 높이 (기본: 720)")
    parser.add_argument("--fps", type=positive_float, default=30, help="요청 FPS (기본: 30)")
    parser.add_argument("--duration", type=positive_float, help="지정한 초 후 자동 종료")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "linux":
            raise RuntimeError("이 예제는 Linux V4L2 카메라용입니다.")
        cameras, issues = discover_cameras()
        print_cameras(cameras)
        for issue in issues:
            print(f"장치 조회 실패: {issue}", file=sys.stderr)
        if args.list:
            return 0 if cameras else 1
        selected = select_camera(cameras, args.device)
        if selected is None:
            return 0
        camera, device = selected
        print(f"선택: {camera.name} ({device})")
        command = [sys.executable, str(Path(__file__)), "--device", str(device)]
        print(f"다음 실행: {shlex.join(command)}", flush=True)
        preview(camera, device, args)
        return 0
    except KeyboardInterrupt:
        print("\n카메라 미리보기를 종료합니다.")
        return 0
    except RuntimeError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
