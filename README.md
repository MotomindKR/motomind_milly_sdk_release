# Motomind Milly SDK

[GitBook 문서](https://motomind.gitbook.io/motomind-dev)

Milly 6축 팔과 그리퍼를 Python 또는 ROS2로 제어합니다.
모든 명령은 **release 루트**에서 실행하며, `MILLY_ABCD`는 실제 제품 ID로 바꾸세요.

## 지원 환경

| 사용 방식 | OS / CPU | Python | 상태 |
| --- | --- | --- | --- |
| Python SDK | Linux x86_64 · Ubuntu 22.04 / 24.04 | 3.10 / 3.11 / 3.12 | 지원 |
| ROS2 Humble | Ubuntu 22.04 / x86_64 | 3.10 | 지원 |
| ROS2 Jazzy | Ubuntu 24.04 / x86_64 | 3.12 | 지원 예정 |

## 시작하기

| 원하는 작업 | 안내 |
| --- | --- |
| 설치·재설치 | [설치](INSTALL.md) |
| Python 예제 실행 | [전체 실행 명령](examples/python/README.md) |
| Python 코드 작성 | [함수별 사용법](SDK_python_guide.md) |
| ROS 드라이버 실행·제어 | [ROS 명령어](SDK_ROS2_guide.md) |
| RViz로 관절 확인 | [모델 확인](SDK_ROS2_guide.md) |
| 제품별 게인·속도 변경 | [프로파일](profiles/README.md) |
| 버전별 변경 사항 | [변경 이력](CHANGELOG.md) |
| 교시장치·Python teleop | [DXL-only / Milly teleop 예제](examples/python/README.md) — teaching wheel 선택 설치 |

같은 로봇에는 제어 프로그램 하나만 실행하세요.
**같은 로봇에 native Python SDK 드라이버와 ROS2 Humble SDK 드라이버를 동시에 실행하지 마세요.**

## 기본 관절 범위

1.0.5에서는 모든 joint의 기존 `safe_position` 최솟값을 0.1 rad 낮추고 최댓값을 0.1 rad 높였습니다.
실측 위치의 안전 범위는 명령 범위 양끝에 각각 **0.15 rad** 여유를 둡니다.
이 안전 범위를 벗어나면 fault와 damping latch가 걸립니다.

| Joint | MIT 명령 범위 [rad] | 실측 안전 범위 [rad] |
| --- | --- | --- |
| joint_1 | -2.80 ~ 2.80 | -2.95 ~ 2.95 |
| joint_2 | -3.20 ~ 0.00 | -3.35 ~ 0.15 |
| joint_3 | -2.75 ~ 0.00 | -2.90 ~ 0.15 |
| joint_4 | -2.42 ~ 2.42 | -2.57 ~ 2.57 |
| joint_5 | -1.84 ~ 1.70 | -1.99 ~ 1.85 |
| joint_6 | -1.55 ~ 1.55 | -1.70 ~ 1.70 |
| gripper | 0.00 ~ 2.11 | -0.15 ~ 2.26 |

`move_mit()`의 위치 명령은 MIT 명령 범위로 제한됩니다. `move_j()`는 `safe_position`을 계획 범위로 사용합니다.
이 범위는 SDK 내부에서 관리하며 사용자 프로파일로 변경할 수 없습니다.
