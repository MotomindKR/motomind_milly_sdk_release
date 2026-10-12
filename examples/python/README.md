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

## 교시장치 — 두 예제

교시장치 SDK는 Milly와 독립된 선택 패키지입니다. 교시장치만 쓸 때는 아래 wheel만 설치합니다.
Milly teleop은 [Milly 설치](../../INSTALL.md) 후 teaching wheel을 추가로 설치하세요.

```bash
python -m pip install dist/teaching/*.whl
```

최초 USB 권한 설정:

```bash
sudo usermod -aG dialout "$USER"
# 로그아웃/로그인하고 터미널·VS Code를 다시 실행
teaching-check-port
```

로그아웃 없이 현재 연결된 장치를 바로 사용하려면 임시로 권한을 설정하세요.

```bash
sudo chmod 777 /dev/ttyUSB0
teaching-check-port
```

이 임시 권한은 USB 재연결 시 초기화될 수 있습니다. `dialout` 설정은 다음 로그인부터 적용됩니다.

**필수 USB 지연 설정:** 예제 실행 전에 `latency_timer`를 **1 ms**로 설정하세요.
교시장치 프로그램을 종료한 상태에서 다음 명령을 실행합니다.

```bash
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
# 출력이 1인지 확인
```

USB를 다시 연결한 뒤에도 값을 확인하고, 1이 아니면 다시 설정하세요.

기본 포트는 `/dev/ttyUSB0`입니다. 두 예제는 `configs/dxl_right_example.json`을 같은 폴더에서 읽습니다.
배열은 1~6축, 그리퍼 순서(ID 40~46)이며 사용자 설정은 세 항목입니다.

| JSON 항목 | 범위 |
| --- | --- |
| `torque_enable` | 각 축 `true` / `false` |
| `current_limit` | 정수 0~800 mA |
| `p_gain` | 정수 0~100 |

기본 설정은 3·4축과 그리퍼만 토크 ON합니다.
`--profile my_teaching.json`으로 수정한 JSON을 지정할 수 있습니다.

```bash
# 1. DXL만: Enter → 선택 축 토크 ON 및 3초 ramp → 위치 출력 → Ctrl+C로 OFF
python examples/python/dxl_only.py

# 2. DXL 토크 ON → Enter → Milly HOLD → 3초 보간 → teleop → Ctrl+C shutdown
python examples/python/milly_teleop.py --product-id MILLY_ABCD
```

위치 변환과 관절별 출력 범위는 SDK 내부에서 관리하며 JSON에서 수정하지 않습니다.
Milly는 Python SDK `move_mit()`로 제어합니다. 팔 6축 KP는 `[30,30,30,15,15,5]`,
KD는 `[1.5,1.5,1.5,1.0,1.0,0.5]`, 그리퍼 KP/KD는 `5.0/0.5`입니다.
이는 교시장치 JSON의 `p_gain`과 별개입니다. `motion.max_vel: 0.5`는 계획 이동용이며
MIT teleop의 속도 제한으로 적용되지 않습니다.
추종 기본 주기는 30 Hz이며 `--rate-hz 30`으로 지정할 수 있습니다.
시작 보간은 실제 경과시간 3초 기준으로 수렴하고 이후 새 위치를 직접 추종합니다.
통신·OS 지연이 있으면 3초 이후 첫 정상 샘플에서 추종으로 전환합니다.
실행 중 `Teleop: ... Hz; DXL step ... ms`로 실제 주기와 DXL 처리 시간을 확인하세요.
시작 전에 두 장치를 비슷한 자세로 맞추고 지지하세요. 보간에는 충돌 검사가 없습니다.
시작 실측 위치는 SDK 안전 범위 안에서 확인하고 명령 범위 경계로 맞춥니다.
안전 범위 밖이거나 피드백이 누락되면 이동을 시작하지 않습니다.
Enter 대기 중에도 DXL을 계속 읽으며, 통신 실패는 시작 취소 또는 Milly shutdown으로 이어집니다.
종료 시 Milly는 damping, 이 예제가 켠 DXL 축은 OFF합니다. 케이블 단절 시 DXL OFF 전송은 보장할 수 없습니다.
