# Python 예제

[설치](../../INSTALL.md) 후 release 루트에서 실행합니다.
`MILLY_ABCD`는 실제 제품 ID로 바꾸고, **예제 하나씩** 실행하세요.

```bash
source .venv/bin/activate
```

## 검색·피드백

```bash
python examples/python/discover_robots.py
python examples/python/motor_state_check.py --product-id MILLY_ABCD --duration 5
```

결과: 제품 ID 검색 / **모터 enable 후** 5초간 피드백 출력.

## 이동 — 원하는 예제 하나 선택

```bash
# 6축 zero 이동 + 그리퍼 닫기
python examples/python/move_j_test.py --product-id MILLY_ABCD --gui=false

# zero 자세의 flange pose로 관절 PTP 이동 + 그리퍼 닫기
python examples/python/move_p_test.py --product-id MILLY_ABCD --gui=false

# 7개 모터를 zero 목표로 3초 MIT ramp
python examples/python/move_mit_test.py --product-id MILLY_ABCD --gui=false
```

## 중력보상

```bash
python examples/python/gravity_float.py --product-id MILLY_ABCD --gui=false
```

결과: 현재 자세에서 FLOAT. **Ctrl+C → shutdown/damping**.
1축과 그리퍼는 `kp=0, kd=0, t_ff=0`입니다.

## 그리퍼

```bash
python examples/python/gripper_test.py --product-id MILLY_ABCD
```

입력: `o` 열기 · `c` 닫기 · 숫자 위치(rad) · `k` 게인 · `s` 상태 · `q` 종료.

`--gui=true`: ROS2와 같은 버튼 없는 모터 조회 GUI. 위치·속도·토크·온도·fault·수신 상태를 표시합니다.
GUI 창을 닫아도 제어는 유지됩니다. 로봇 종료는 예제 터미널에서 Ctrl+C로 진행합니다.
Enter 입력 전에도 Ctrl+C로 종료할 수 있습니다. `[stop] SDK shutdown completed`와 셸 프롬프트 복귀를 확인한 뒤 다른 예제를 실행하세요. Ctrl+Z는 종료가 아닌 일시 정지입니다.
`--help`: 추가 옵션.
검색 외 예제는 실제 모터를 enable합니다. 충돌 검사는 없으며 종료 damping은 자세 고정이 아닙니다.
무구동 표시는 [ROS description](../../SDK_ROS2_guide.md)을 사용하세요.
