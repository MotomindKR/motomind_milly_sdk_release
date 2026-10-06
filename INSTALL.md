# 설치

[지원 환경](README.md#지원-환경)을 확인하고 release 루트에서 실행하세요.
Python 직접 사용과 ROS 중 필요한 경로를 선택합니다.

## Python SDK

```bash
python3.10 -m venv .venv       # 3.11 / 3.12도 사용 가능
source .venv/bin/activate
python -m pip install --upgrade pip
python scripts/ci/install_wheels.py
python -c "import motomind_milly as mm; print(mm.__version__)"
```

결과: 현재 Python에 맞는 SDK·모델 wheel 설치, 버전 출력.
새 터미널에서는 `source .venv/bin/activate`를 실행합니다.
동일 버전 재설치도 `python scripts/ci/install_wheels.py`로 진행합니다.

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
