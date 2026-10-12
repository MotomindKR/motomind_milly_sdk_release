# Milly SDK 1.0.1

- 교시장치용 독립 Python SDK와 DXL-only / Milly teleop 예제를 추가했습니다. 각 축의 토크, 전류 상한, P gain을 JSON으로 설정할 수 있습니다.
- teleop 예제는 시작 시 3초 보간을 수행하고, 교시장치 통신 오류가 발생하면 Milly shutdown을 호출합니다. DXL 통신량을 줄여 추종 응답도 개선했습니다.
- 교시장치를 움직이며 가상 Milly의 자세를 확인하는 RViz 미리보기를 추가했습니다.
- Linux USB 지연을 1 ms로 설정하는 초기 설정 스크립트를 제공합니다.
