# 설치

[지원 환경](README.md#지원-환경)을 확인하고 release 루트에서 실행하세요.
Python 직접 사용과 ROS 중 필요한 경로를 선택합니다.

## Python SDK

`X`는 사용할 Python 버전에 맞게 `10`, `11`, `12` 중 하나로 바꾸세요.
해당 Python이 설치되어 있어야 하며, venv 패키지도 같은 버전으로 설치합니다.

```bash
sudo apt install -y python3.X-venv
python3.X -m venv .venv       # 3.10 / 3.11 / 3.12 사용 가능
source .venv/bin/activate
python -m pip install --upgrade pip
python scripts/ci/install_wheels.py
python -c "import motomind_milly as mm; print(mm.__version__)"
```

결과: 현재 Python에 맞는 SDK·모델 wheel 설치, 버전 출력.
새 터미널에서는 `source .venv/bin/activate`를 실행합니다.
동일 버전 재설치도 `python scripts/ci/install_wheels.py`로 진행합니다.

교시장치도 사용하면 독립 teaching wheel을 함께 설치합니다:

```bash
python scripts/ci/install_wheels.py --with-teaching
```

교시장치만 사용하는 경우에는 Milly 없이 `python -m pip install dist/teaching/*.whl`만 실행하세요.
[교시장치 예제와 USB 권한·필수 지연 설정](examples/python/README.md)을 따릅니다.

## ROS2 Humble

Ubuntu 22.04 / x86_64 / ROS2 Humble 환경에서 실행합니다.

```bash
bash scripts/setup_ros_humble.sh
source scripts/ros_env.sh
```

결과: `.venv_ros`에 SDK 설치 → ROS 빌드 → 연결 없이 설치 검사.
재설치도 같은 명령입니다. 실행 중인 드라이버는 먼저 종료하세요.
새 터미널마다 `source scripts/ros_env.sh`를 실행합니다.

## CAN 연결

제어 프로그램이 **종료된 상태**에서 실행하세요. can0을 재설정합니다.

```bash
bash scripts/set_can_interface.sh
ip -details link show can0
python examples/python/discover_robots.py
```

결과: CAN 1 Mbps, 연결된 제품 ID와 인터페이스 출력.

다음: [Python 예제](examples/python/README.md) · [ROS 명령어](SDK_ROS2_guide.md)
