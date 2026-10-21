# 변경 이력

사용자에게 영향을 주는 변경 사항을 최신 버전부터 기록합니다.

## 1.0.3

- 교시장치 SDK 0.1.2를 함께 제공합니다. 그리퍼 복원 목표를 2.4 rad, 기본 P gain을 150으로 조정했으며, 반환 위치는 기존처럼 0~2.11 rad로 제한합니다.
- 교시장치 JSON에서 그리퍼 P gain을 0~150 범위로 설정할 수 있습니다. 팔 P gain은 0~100, 전류 상한은 0~800 mA입니다.
- 토크 준비 시 이미 설정된 DXL 동작 모드 5를 유지하도록 개선했습니다.
- Python·ROS2 교시장치 예제의 기본 포트를 `/dev/ttyACM0`으로 통일했습니다. 다른 포트도 직접 지정할 수 있습니다.
- 설치 가이드에 SDK 호환 버전 표를 추가하고, teleop 예제에 추종성을 높이는 선택 KP/KD 값을 안내합니다. 예제 코드의 기본 Milly KP/KD는 유지됩니다.

## 1.0.2

- Python SDK 지원 환경에 Ubuntu 24.04를 추가했습니다.
- Python 3.10·3.11·3.12 가상환경 생성과 venv 패키지 설치 안내를 보완했습니다.
- 교시장치의 ttyUSB / ttyACM 포트를 확인하고 Python·RViz 예제에 지정하도록 안내합니다.
- USB 설정 스크립트에 `--port`를 추가했습니다. FTDI ttyUSB는 재연결 후 지연 값이 1 ms인지 확인하며, ttyACM은 해당 지연 설정을 건너뜁니다.
- 교시장치 SDK 0.1.1의 패키지 설명을 사용자 안내로 정리했습니다.
- ROS 업데이트 후 구버전 패키지 정보가 남아 교시장치 미리보기가 시작되지 않는 문제를 수정했습니다.

## 1.0.1

- Milly·ROS와 독립된 교시장치 Python SDK를 추가했습니다.
- DXL-only / Milly MIT teleop 예제를 추가했습니다. 각 축의 토크, 전류 상한, P gain을 JSON으로 설정할 수 있습니다.
- teleop 시작 시 3초 보간을 수행하고, 교시장치 통신 오류가 발생하면 Milly shutdown을 호출합니다. DXL 통신량을 줄여 추종 응답을 개선했습니다.
- 교시장치 위치로 가상 Milly 자세를 확인하는 RViz 미리보기를 추가했습니다.
- Linux FTDI USB 지연을 1 ms로 설정하는 초기 설정 스크립트를 추가했습니다.

## 1.0.0

- Python SDK와 ROS2 Humble 인터페이스를 제공합니다.
- Linux x86_64 / Python 3.10·3.11·3.12용 SDK wheel을 제공합니다.
- Python·ROS2 설치 및 실행 가이드를 분리했습니다.
- 배포 파일 검증과 Python·ROS2 CI를 구성했습니다.

1.0.0 이전 배포 기록은 [GitHub Releases](https://github.com/MotomindKR/motomind_milly_sdk_release/releases)에서 확인할 수 있습니다.
