# Motomind Milly SDK 정리

상세 설치·예제는 [INSTALL.md](INSTALL.md), [README.md](README.md) 참고.

## 0. 설치 / 실행 전제

`motomind_milly`는 Milly 6축 팔(+그리퍼 모터, Robstride CAN)용 Python SDK.
C++ 코어(pybind11) 위에서 CAN 통신, 상태 읽기, 모션 제어(호스트측 계획/IK)를 지원.
Python 3.10+.

```bash
python -m pip install dist/linux_x86_64/python3.X/*.whl   # 파이썬 버전 폴더 선택 (Linux, 3.10/3.11/3.12)
```

Linux에서는 CAN을 먼저 올린다 (bitrate는 모터와 일치, 1 Mbit/s):

```bash
./scripts/set_can_interface.sh
```

**Windows** — WIP

## 1. 기본 Import

```python
import motomind_milly as mm
from motomind_robot_model import RobotModel     # FK/IK/중력 (robotmodel extra)
```

| 객체 | 역할 |
| --- | --- |
| `mm.create_arm(product_id)` | 제품 ID로 로봇을 찾아 연결된 Arm 생성 |
| `RobotModel(mm.milly_urdf())` | SDK wheel에 포함된 Milly URDF로 FK/IK/중력토크 계산 |
| `mm.enable_logging()` | SDK 로그 출력 (상태 전이·fault는 자동 기록) |

## 2. 인스턴스 생성 / 연결

### 제품 경로 — 각인된 제품번호로

로봇마다 각인된 제품번호(예: `MILLY_ABCD`)가 있고, 로봇의 LED 보드에도 같은
값이 저장되어 있다. SDK가 모든 CAN 버스를 조회해 **전체 일치**할 때만 연다
(fail-closed, 우회 없음).

```python
arm = mm.create_arm("MILLY_ABCD")   # 연결까지 완료된 Arm 반환
```

**로봇 등록** — `profiles/` 디렉토리에 제품번호와 같은 이름의 튜닝 파일을 두되,
**기본값과 다른 것만** 적는다. `profiles/MILLY_SAMPLE.yaml`을 복사해 시작한다:

```bash
export MOTOMIND_CONFIG_DIR="$PWD/profiles"       # 로봇 파일들이 있는 디렉토리
cp profiles/MILLY_SAMPLE.yaml profiles/MILLY_ABCD.yaml
# MILLY_ABCD.yaml 에서 바꿀 키만 남긴다 (나머지는 DEFAULT 상속), 예:
#   motion:
#     kp: [30, 30, 30, 15, 15, 5]
```

튜닝은 **3단 레이어**다: 내장 정본(모터/한계/안전 — 사용자 불가) + 번들
`MILLY_DEFAULT.yaml`(기본 튜닝) + 로봇 파일(그 위에 **키 단위로 덮어씀**). 로봇
파일이 생략한 키/섹션은 DEFAULT에서 **상속**된다 — 빈 파일(또는 파일 없음)이면
전부 DEFAULT 값을 쓴다. 허용된 키만 쓸 수 있고, 오타·범위 밖 값은 로드 시 에러다.
`MOTOMIND_CONFIG_DIR`을 안 정하면 SDK는 설치된 패키지의 `profiles/`를 본다.

**로봇이 늘어나면**: 같은 디렉토리에 파일만 추가하면 된다 (N대 = N파일).

```text
profiles/                # = $MOTOMIND_CONFIG_DIR
├── MILLY_DEFAULT.yaml   # 상속 기준(참고용)
├── MILLY_ABCD.yaml      # 1호기
└── MILLY_A1B2.yaml      # 2호기
```

```python
arm1 = mm.create_arm("MILLY_ABCD")   # 각자 독립 인스턴스 —
arm2 = mm.create_arm("MILLY_A1B2")   # 버스는 SDK가 자동으로 찾음
```

연결된 로봇 확인(제품번호/버튼/LED):

```bash
.venv/bin/motomind-milly-robots
#   MILLY_ABCD  on can0   button=0   led=sky-blue/normal
```

```python
mm.list_robots()    # [RobotId(interface, name, button_state, led_fault)]
```

## 3. 연결 상태 / 통신 상태 확인

```python
print(arm.is_ok())                  # fault 없고 제어루프 에러 없음
print(arm.state())                  # Idle/Enabled/Running/Fault/Shutdown
print(arm.manager.fault_reason())   # fault 사유 (예: 'electronic_emergency_stop')
arm.disconnect()
```

모든 상태 전이와 fault는 백그라운드 watcher가 **자동으로 로그**하므로
(`enable_logging()` 시) 별도 폴링 없이도 놓치지 않는다.

## 4. 상태 읽기 API

```python
ja = arm.get_joint_angles()         # [j1..j6] rad (피드백 없으면 None 항목)

for s in arm.states():              # 모터별 전체 상태
    print(s.id, s.position, s.velocity, s.torque, s.temperature, s.fault_bits)

print(arm.get_flange_pose())        # [x,y,z, roll,pitch,yaw] m/rad — robot model 필요
```

## 5. 기본 설정 API

```python
# SDK release wheel 안의 motomind_milly/robot/MILLY.urdf를 정확히 사용한다.
arm.set_robot_model(RobotModel(mm.milly_urdf()))
arm.set_max_vel(0.5)                # move_j/p 기본 피크 속도 [rad/s]
```

- speed percent(0~100)는 **의도적으로 없음** — 속도는 rad/s로 직접 지정,
  사용자 프로파일 `motion.max_vel`은 최대 `2.0 rad/s`이다.
- `create_arm()`으로 열면 로봇 튜닝 파일의 `motion.kp/kd/max_vel`이
  자동으로 이 기본값들에 적용된다 (호출 시 명시한 인자가 우선).

## 6. 모션 제어 API

### Enable / Disable / E-stop

```python
arm.enable()                        # 전체 모터 enable (FsmResult 반환)
arm.start_control_loop(100.0)       # 제어루프 시작 — move_* 전에 필수

arm.electronic_emergency_stop()     # yaml manual_fault 규칙(감쇠 정지) — 천천히 내려감
arm.shutdown()                      # ★ 안전한 종료 — yaml exit 규칙(damping latch) 실행
arm.disable()                       # ⚠ 토크 즉시 차단 → 팔이 낙하할 수 있음
```

**프로그램을 끌 때는 `shutdown()`을 쓰세요.** `shutdown()`은 yaml의 `exit`
규칙(기본 damping latch)을 실행해 팔이 **감쇠하며 서서히 잡히도록** 합니다.
`disable()`은 토크를 즉시 끊어 **팔이 중력으로 떨어질 수 있습니다** — 사람이
팔을 붙잡고 있거나 안전한 자세일 때, 의도적으로 힘을 뺄 때만 쓰세요.
(`create_arm` 경로에서는 `shutdown()`이 supervisor도 함께 정지시킵니다.)

**dead-man과 supervisor**: 제어루프가 켜지면 명령이 100ms(yaml
`command_update_timeout`) 이상 끊길 때 자동으로 damping latch(감쇠 정지)가
걸린다. 제품 경로(`create_arm`)는 `enable()` 시 supervisor를 자동으로 시작한다.
supervisor는 **유일한 명령 전송자**로서 이동 후에도 목표 자세를 계속 HOLD한다:

```python
arm.enable()
arm.start_control_loop(100.0)       # CAN 송신 주기 [Hz]
arm.start_supervisor(rate_hz=100.0) # 명령 갱신 주기 [Hz], 기본 100, 범위 [20, 500]

arm.move_j([...])             # supervisor 경유 — 끝나면 목표 자세를 계속 HOLD
arm.float_mode()              # 중력보상 ON — 팔이 back-drivable(손으로 끌기), robot model 필요
arm.hold_mode()               # 중력보상 OFF — 현재 자세 강성 HOLD
```

`start_control_loop(rate)`(CAN 송신 주기)와 `start_supervisor(rate_hz)`(명령
갱신 주기)는 별개의 설정이다. supervisor rate는 [20, 500] Hz로 제한된다.

`set_robot_model()`은 사전 세팅된 calibration 파일 `milly_cal.yaml`을 자동 적용한다.

사용자 제품 경로는 `mm.create_arm("MILLY_ABCD")`로만 시작한다. supervisor 없이
명령을 직접 전송하는 경로는 진단·개발 전용이며 사용자 API로 제공하지 않는다.

### Joint motion: `move_j`

```python
arm.move_j([0.0, 0.4, 0.4, 0.0, 0.3, 0.0], max_vel=0.3)   # rad, 블로킹
```

- 실측 피드백에서 시작하는 큐빅 궤적을 잘게 스트리밍. 완료 후 소요시간(s) 반환.
- `move_j`와 `move_p`도 `move_mit`와 같은 제품 프로파일의 `kp/kd`를 기본으로 쓴다.
- 목표가 허용범위(safe_position/URDF) 밖이면 **조용히 clamp하지 않고
  `ValueError`로 거부**.

### Cartesian PTP: `move_p`

```python
arm.move_p([-0.001, 0.066, 0.391, -1.87, -0.09, -3.1], max_vel=0.2)
# [x,y,z, roll,pitch,yaw] m/rad — Pinocchio IK, 현재 자세를 시드로 사용
```

IK 실패/안전범위 밖 해는 예외로 거부. `set_robot_model()` 선행 필요.

`move_j`와 `move_p`는 명령을 보내기 전에 전체 관절 경로를 exact collision mesh로
검사한다. 시작 자세에 이미 있던 접촉을 제외하고 새 self-collision이 예측되면 `RuntimeError`로 거절하며, supervisor의 기존 HOLD/MIT/FLOAT
상태는 바꾸지 않는다. 릴리스 폴더 또는 그 하위 폴더에서 실행하면
`milly_description/`을 자동 탐색한다. 다른 위치에 설치했다면
`MOTOMIND_MILLY_DESCRIPTION_DIR`에 해당 `milly_description` 경로를 지정한다.

## 7. Kinematics API (FK)

- FK: `arm.fk(joints)` / `arm.get_flange_pose()` — **flange(link_6)** 기준 pose.
- IK(pose → 관절각)는 **`move_p`로** 사용한다.

pose 기준은 **link_6(팔 끝 장착면)**이라 그리퍼 끝은 포함하지 않는다. `move_p`로 pose를 주면 flange(link_6)가 그 위치로 간다.

## 8. Teaching (드래그)

**중력보상 FLOAT**로 팔을 손으로 끌어 자세를 잡는 back-drivable 드래그가 가능하다
(§6 supervisor의 `arm.float_mode()` ON / `arm.hold_mode()` OFF). 물리 버튼 토글은 §12.

## 9. 저수준 제어 API

### MIT single joint: `move_mit`

```python
arm.move_mit(1, position=0.0, velocity=0.0, kp=10.0, kd=0.8, torque_feedforward=0.0)
# torque = kp*(p_des-p) + kd*(v_des-v) + t_ff
```

`kp`와 `kd`를 생략하면 `MILLY_DEFAULT.yaml`의 기본값을 사용하고, 해당 제품 ID의
yaml 파일이 있으면 그 파일의 `motion`(1~6축) 또는 `gripper`(7축) 값이 적용된다.
호출 시 명시한 값만 해당 축의 프로파일 기본값을 덮어쓴다.

`move_mit`는 한 번에 **모터 하나**의 최신 명령을 갱신한다. 명령은 supervisor가
매 주기 전송하며, MIT 명령을 받지 않은 다른 모터는 현재 자세를 HOLD한다. 같은
모터에 다시 호출하면 최신 값으로 바뀌고, 다른 모터에 호출하면 그 모터의 MIT
명령도 추가된다.

MIT 명령은 `hold_mode()`(현재 자세 HOLD), `float_mode()`(중력보상), `move_j()` 또는
`move_p()`로 전환하기 전까지 유지된다. `move_mit`는 supervisor가 실행 중일 때만
사용할 수 있다. 잘못된 gain은 충격/진동을 만들 수 있으며 yaml `command_limit`이
kp/kd/토크의 상한을 적용한다.

> 중력보상은 §6/§8의 `arm.float_mode()`(ON) ⇄ `arm.hold_mode()`(OFF)로만 제어할 수 있다.

## 10. Limit / Safety / Calibration

코어의 안전 플러그인 체인이 매 명령/피드백을 검사한다. 전체 카탈로그 (기본값은 내장 정본 기준):

| 플러그인 | 언제 동작하나 | 기본 반응 | 튜닝 |
| --- | --- | --- | --- |
| `command_limit` | 명령의 kp/kd/토크/위치가 모터 한계를 벗어나면 한계값으로 클램프 | warning (로그만, 클램프는 항상 수행) | severity, fault_reaction |
| `command_position_step_limit` | 위치 명령이 **실측 위치**에서 3 rad 이상 점프 (폭주 명령 방지) | fault → damping_latch | severity, fault_reaction |
| `safe_position` | 관절 실측이 안전범위(safe_position) 이탈 | fault → damping_latch | ✕ (고정) |
| `command_update_timeout` | 호스트가 100ms 이상 새 명령을 안 보냄 (dead-man) | fault → damping_latch | timeout_ms 50~500 |
| `stale_feedback` | 모터 피드백이 250ms 이상 끊김 (전원/배선 상실) | fault → damping_latch | timeout_ms 50~500 |
| `temperature_warning` | 모터 온도 70 °C 초과 | warning (로그) | threshold_c 40~100 |
| `temperature_fault` | 모터 온도 90 °C 초과 | fault → damping_latch | threshold_c 60~100 |
| `motor_fault` | 모터 자체 fault 비트 보고 (과전류 등) | fault → damping_latch | ✕ (고정) |

**튜닝 방법** — 로봇 튜닝 파일(`MILLY_XXXX.yaml`)의 `safety` 섹션. 표의 "튜닝"
열에 있는 키만 허용되며 그 외(safe_position, motor_fault, 한계값, action)는
시도 자체가 로드 에러다. 값 규칙:

- `severity`: `warning`(로그) | `fault`(리액션 실행) — 검사를 끄는 값(ignore)은
  제공하지 않음
- `fault_reaction`: `freeze_command_stream`(마지막 명령 유지) |
  `damping_latch`(감쇠 정지 — 기본, 팔이 천천히 내려앉음) |
  `hard_disable`(즉시 토크 차단 — **팔이 떨어짐**, 용도 확실할 때만) —
  무반응 값(none)은 제공하지 않음
- `temperature_warning`은 `temperature_fault`보다 낮아야 함.

```yaml
safety:
  command_update_timeout: {timeout_ms: 200}
  temperature_fault: {threshold_c: 80}
```

fault 후 복구는 `arm.recover()`(→ Idle, 무여기) 후 `arm.enable()`(현재 실측
자세에서 다시 홀드). 안전범위 밖으로 처졌으면 수동 재배치 필요. damping latch의
세기는 모터별 `damping_kd`(정본 고정).

- 경로 자가충돌 검사: `RobotModel.enable_self_collision()` + `self_collides(q)`
  (정밀 메시, aging 테스트가 사용).

## 11. Gripper — 위치(임피던스) 제어

`init_effector`로 그리퍼 모터(config의 `joint`/`name` ==
`"gripper"`, 기본 7번)를 별도 핸들로 빼서 위치제어한다. supervisor 명령
스트림을 타므로 dead-man latch 없이 홀드·이동한다 (create_arm → enable()이
supervisor를 자동 기동).

```python
grip = arm.init_effector()          # 기본 joint="gripper"
grip.move(-1.0)                     # 목표 위치[rad] (range로 clamp), 임피던스 홀드
grip.open()                        # 완전 열림 (Milly: -2.3 rad)
grip.close()                       # 완전 닫힘 (Milly: 0.0 rad)
grip.move(-1.0, kp=8, kd=0.3)      # 홀드 강도 조절(선택)
grip.position                      # 현재 측정 위치[rad] (피드백 없으면 None)
grip.range                         # (lo, hi) — 정본 config의 위치 한계
```

- Milly: `open` = -2.3 rad(range 하단), `close` = 0.0 rad(range 상단).
- 기본 홀드 강도는 프로파일 `gripper: {kp, kd}` 로 조정 (범위 kp 0..50, kd 0..5).
  낮은 kp = 부드러운 그립. per-call `move(pos, kp=, kd=)` 가 우선.
- supervisor가 안 돌면 `move`가 에러(`supervisor not running`) — enable() 먼저.

---

## 반환값 레퍼런스 (함수별 type / 예시)

주요 함수의 반환 타입과 예시. 반환이 `None`이면 부수효과만 있는 함수다.

**생성 / 발견**

| 함수 | 반환 타입 | 예시 |
| --- | --- | --- |
| `create_arm(id)` | `Arm` | 연결까지 완료된 Arm 객체 |
| `list_robots()` | `List[RobotId]` | `[RobotId(interface='can0', name='MILLY_ABCD', button_state=0, led_fault=0)]` |
| `arm.init_effector()` | `Gripper` | 그리퍼 핸들 객체 |

**상태 읽기**

| 함수 | 반환 타입 | 예시 |
| --- | --- | --- |
| `arm.is_ok()` | `bool` | `True` |
| `arm.state()` | `MotorManagerState` (enum) | `MotorManagerState.Running` |
| `arm.get_joint_angles()` | `List[Optional[float]]` | `[0.0, 0.41, 0.40, 0.0, 0.30, 0.0]` (피드백 없는 관절은 `None`) |
| `arm.states()` | `List[MotorState]` | `[MotorState(id=1, position=0.0, velocity=0.0, torque=0.12, temperature=31.5, fault_bits=0), …]` |
| `arm.get_flange_pose()` / `arm.fk(q)` | `List[float]` (6개) | `[-0.001, 0.066, 0.391, -1.87, -0.09, -3.10]` = `[x,y,z, roll,pitch,yaw]` |

**모션 / 수명주기**

| 함수 | 반환 타입 | 예시 |
| --- | --- | --- |
| `enable()` `disable()` `shutdown()` `recover()` `electronic_emergency_stop()` | `FsmResult` | `FsmResult(ok=True, message='enabled')` → `res.ok` / `res.message` |
| `start_control_loop()` `stop_control_loop()` | `FsmResult` | `FsmResult(ok=True, …)` |
| `move_j(...)` | `float` | `2.34` — 이동 소요 시간 [s] |
| `move_p(...)` | `float` | `1.80` — 이동 소요 시간 [s] (내부 IK 후 move_j) |
| `float_mode()` `hold_mode()` | `None` | — (모드 전환만) |

**설정 / 그리퍼**

| 함수 | 반환 타입 | 예시 |
| --- | --- | --- |
| `set_max_vel(v)` / `set_robot_model(rm)` | `None` | — |
| `grip.move(pos)` / `open()` / `close()` | `float` | `-2.30` — clamp된 목표 위치 [rad] |
| `grip.position` | `Optional[float]` | `-1.15` (피드백 없으면 `None`) |
| `grip.range` | `Tuple[float, float]` | `(-2.3, 0.0)` |

**반환 객체 구조**

- **`FsmResult`** — `.ok`(bool), `.message`(str) : 전이 성공 여부 + 사유
- **`MotorState`** — `.id` `.position` `.velocity` `.torque` `.temperature` `.fault_bits`
- **`RobotId`** — `.interface` `.name`(제품ID) `.button_state` `.led_fault`
- **`MotorManagerState`** (enum) — `Idle` / `Enabled` / `Running` / `Fault` / `Shutdown`

---

## 부록: 도구 / 예제

```bash
.venv/bin/motomind-milly-robots                    # 연결된 로봇 조회 (시리얼 비표시)
```

```python
from motomind_milly.monitor import MotorMonitor

# mm.create_arm("MILLY_ABCD") 뒤, arm.enable() 전에 1회 실행한다.
MotorMonitor(arm.manager, arm._config, poll_ms=250).start()
```

GUI는 같은 Arm/manager를 사용하며 모터 상태와 E-STOP을 제공한다. 창을 닫아도 로봇은
종료되지 않으므로, 프로그램 종료에는 반드시 `arm.shutdown()`을 사용한다.

| 예제 | 용도 |
| --- | --- |
| `examples/discover_robots.py` | 연결된 로봇 발견 + 제품ID(모델명) 조회 — **제일 먼저** |
| `examples/motor_state_check.py` | 모터 통신/읽기 확인 (`--move` 부드러운 모션) |
| `examples/move_j_test.py` | 6축 0 rad move_j 후 gripper를 0 rad(닫힘)로 이동 (GUI 기본, `--gui=false`로 해제) |
| `examples/move_p_test.py` | 0 rad 관절 자세의 flange pose로 move_p 후 gripper를 0 rad(닫힘)로 이동 (GUI 기본, `--gui=false`로 해제) |
| `examples/move_mit_test.py` | 6축과 gripper를 3초간 0 rad로 MIT warm-up 후 damping latch (GUI 기본, `--gui=false`로 해제) |
| `examples/gripper_test.py` | 그리퍼 위치제어 실기 테스트 |
| `examples/gravity_float.py` | 중력보상 FLOAT 드래그 데모 (GUI 기본, `--gui=false`로 해제) |
| `examples/button_test.py` | 버튼/LED 토글 + 신뢰성(miss율) 소크 (`--with-arm`) |
