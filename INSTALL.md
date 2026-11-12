# 설치

[지원 환경](README.md#지원-환경)을 확인하고 release 루트에서 실행하세요.
Python 직접 사용과 ROS 중 필요한 경로를 선택합니다.

Git으로 받은 경우 모델 파일도 내려받아야 합니다. 최초 1회 실행하세요:

```bash
sudo apt update
sudo apt install -y git-lfs
git lfs install
git lfs pull
```

압축 파일은 GitHub Releases의 배포 bundle을 사용하세요.
GitHub의 **Code → Download ZIP**에는 실제 모델 대신 LFS 포인터가 들어갈 수 있습니다.

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

그리퍼 USB 카메라의 영상 창을 사용하면 GUI 지원 OpenCV를 별도로 설치합니다:

```bash
python -m pip install 'opencv-python>=4.8,<5'
python examples/python/camera_preview.py
```

카메라만 볼 때는 Milly·Teaching SDK 설치 없이 위 명령만으로 실행할 수 있습니다.
[납품 카메라 선택 기준·고정 경로·문제 해결](examples/python/README.md#그리퍼-usb-카메라--실시간-영상)을 확인하세요.

### Milly SDK · 교시장치 SDK 버전 조합

같은 release에 포함된 wheel 조합을 권장합니다. 두 SDK의 버전 번호는 독립적으로 관리합니다.

| Release 버전 | Milly SDK | Teaching SDK |
| --- | --- | --- |
| 1.1.2 Release | 1.1.2 | 0.1.3 |
| 1.1.1 Release | 1.1.1 | 0.1.3 |
| 1.1.0 Release | 1.1.0 | 0.1.2 |
| 1.0.6 Release | 1.0.6 | 0.1.2 |
| 1.0.5 Release | 1.0.5 | 0.1.2 |
| 1.0.4 Release | 1.0.4 | 0.1.2 |
| 1.0.3 Release | 1.0.3 | 0.1.2 |
| 1.0.2 Release | 1.0.2 | 0.1.1 |

Python용 환경과 ROS용 환경에서 교시장치를 함께 사용하면 Teaching SDK도 같은 버전으로 맞추세요.
재설치하면 별도 업데이트한 패키지도 해당 release에 포함된 버전으로 맞춰집니다.
교시장치만 사용할 때는 Milly SDK 설치가 필요하지 않습니다.

## ROS2 Humble

Ubuntu 22.04 / x86_64 / ROS2 Humble 환경에서 실행합니다.
ROS Humble은 먼저 설치되어 있어야 합니다. `/opt/ros/humble/setup.bash`가 없다면
[ROS Humble 공식 Ubuntu 설치 안내](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html)를 먼저 따르세요.
이 스크립트는 설치된 Humble 위에 SDK와 Milly ROS 패키지를 구성합니다.
Python SDK용 `.venv`나 Conda를 활성화하지 않은
새 Bash 터미널에서 release 루트로 이동한 뒤 실행하세요. 시스템 Python 3.10으로 `.venv_ros`를 만듭니다.

```bash
bash scripts/setup_ros_humble.sh
source scripts/ros_env.sh
```

결과: `.venv_ros`에 SDK 설치 → ROS 빌드 → 연결 없이 설치 검사.
재설치도 같은 명령입니다. 실행 중인 드라이버는 먼저 종료하세요.
ROS 빌드 후 남은 구버전 패키지 정보를 정리하고 `teaching_preview` 등 실행 항목도 검사합니다.
새 터미널마다 `source scripts/ros_env.sh`를 실행합니다.

설치가 실패하면 먼저 출력된 오류를 해결하고 설치 명령을 다시 실행하세요.
`.venv_ros` 또는 ROS 빌드가 누락되었다는 안내는 앞선 설치가 완료되지 않았다는 뜻입니다.
`Git LFS model data is missing`는 위의 `git lfs pull`로 해결합니다.
연결 없이 설치 상태를 다시 검사하려면 환경 활성화 후 `python scripts/check_ros_install.py`를 실행하세요.

## CAN 연결

제어 프로그램이 **종료된 상태**에서 실행하세요. can0을 재설정합니다.

```bash
bash scripts/set_can_interface.sh
ip -details link show can0
python examples/python/discover_robots.py
```

결과: CAN 1 Mbps, 연결된 제품 ID와 인터페이스 출력.

다음: [Python 예제](examples/python/README.md) · [ROS 명령어](SDK_ROS2_guide.md)
