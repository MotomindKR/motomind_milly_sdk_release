# Milly SDK 1.0.2

- Python SDK 지원 환경에 Ubuntu 24.04를 추가하고, Python 3.10·3.11·3.12 가상환경 설치 안내를 보완했습니다.
- 교시장치의 ttyUSB / ttyACM 포트를 확인한 뒤 Python·RViz 예제에 지정하도록 안내합니다.
- USB 설정 스크립트에 `--port`를 추가했습니다. FTDI ttyUSB는 재연결 후 지연 값이 1 ms인지 확인하며, ttyACM은 해당 지연 설정을 건너뜁니다.
- ROS 업데이트 후 구버전 패키지 정보가 남아 교시장치 미리보기가 시작되지 않는 문제를 수정했습니다.
