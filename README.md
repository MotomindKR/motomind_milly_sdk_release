# Motomind Milly SDK

[GitBook 문서](https://motomind.gitbook.io/motomind-dev)

Milly 6축 팔과 그리퍼를 Python 또는 ROS2로 제어합니다.
모든 명령은 **release 루트**에서 실행하며, `MILLY_ABCD`는 실제 제품 ID로 바꾸세요.

## 지원 환경

| 사용 방식 | OS / CPU | Python | 상태 |
| --- | --- | --- | --- |
| Python SDK | Linux x86_64 · Ubuntu 22.04 검증 | 3.10 / 3.11 / 3.12 | 지원 |
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

같은 로봇에는 제어 프로그램 하나만 실행하세요.
**같은 로봇에 native Python SDK 드라이버와 ROS2 Humble SDK 드라이버를 동시에 실행하지 마세요.**
