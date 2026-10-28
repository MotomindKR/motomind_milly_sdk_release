# Python SDK — 함수별 사용법

[설치](INSTALL.md) · [전체 예제 명령](examples/python/README.md) · [제품별 설정](profiles/README.md) · [관절·게인·명령 범위](milly_description/README.md)
각도 rad, 속도 rad/s, 토크 N·m. pose는 base 기준 flange `[x,y,z,roll,pitch,yaw]` (m/rad)입니다.
같은 로봇에는 제어 프로그램 하나만 실행하세요. 이동 API에는 충돌 검사가 없습니다.

## 1. 연결 → enable → 이동 → 종료

아래 코드를 `move_zero.py`로 저장하고 `MILLY_ABCD`를 실제 제품 ID로 바꾸세요.

```python
import motomind_milly as mm
from motomind_robot_model import RobotModel

mm.enable_logging()
arm = mm.create_arm("MILLY_ABCD")
try:
    arm.set_robot_model(RobotModel(mm.milly_urdf()))
    input("Enter: 현재 자세에서 enable ")
    result = arm.enable()
    if not result.ok:
        raise RuntimeError(result.message)
    input("Enter: 6축 zero 이동 ")
    duration = arm.move_j([0.0] * 6, max_vel=0.2)
    print(f"궤적 전송 완료: {duration:.2f} s")
    input("Enter: 종료 ")
finally:
    arm.shutdown()
```

```bash
source .venv/bin/activate
python move_zero.py
```

결과: 현재 자세 HOLD → Enter 후 zero 이동 → 종료 damping.
이동 반환은 궤적 전송 완료이며 실측 도달은 피드백으로 확인합니다.
이하 함수는 위 코드의 enable 이후, shutdown 전에 사용하세요.

## 2. 상태 읽기

```python
print(arm.state())                 # Idle / Enabled / Running / Fault / Shutdown
print(arm.is_ok())                 # bool
print(arm.get_joint_angles())      # 6축 rad; 미수신 항목은 None
print(arm.get_flange_pose())       # flange pose, m/rad
for s in arm.states():
    print(s.id, s.position, s.velocity, s.torque, s.temperature, s.fault_bits)
```

## 3. 관절 이동·Cartesian 이동

```python
arm.set_max_vel(0.2)              # 이후 기본 속도
arm.move_j([0.0] * 6)             # 6축 목표, gripper 제외
pose = arm.fk([0.0] * 6)          # zero 자세의 flange pose, 이동 없음
arm.move_p(pose, max_vel=0.2)      # IK 후 관절 PTP, 직선 이동 아님
```

[관절·속도 범위와 게인 적용 조건](milly_description/README.md)을 확인하세요. 목표 범위 이탈·IK 실패는 예외로 거부합니다.
`move_j`·`move_p`는 완료까지 대기하고 소요시간(s)을 반환합니다.

## 4. 중력보상 ON / OFF

팔을 지지한 상태에서 실행하세요. 모델 설정은 enable 전에 완료합니다.

```python
arm.float_mode()                  # ON: 현재 자세에서 FLOAT
# ... 손으로 자세 조정 ...
arm.shutdown()                    # OFF: damping 및 연결 종료
```

FLOAT 세기·게인은 사용자 인자로 제공하지 않습니다.
1축·그리퍼는 `kp=0, kd=0, t_ff=0`. [나머지 축 기본값](milly_description/README.md)
다시 ON하려면 Arm 생성 → 모델 설정 → enable을 반복합니다.
`arm.hold_mode()`는 현재 자세 HOLD이며 OFF/shutdown과 다릅니다.

## 5. 그리퍼

```python
grip = arm.init_effector()
grip.open()                       # 2.11 rad
grip.close()                      # 0.0 rad
grip.move(1.0)                    # 범위 내 목표 반환, rad
print(grip.position)              # 실측 rad 또는 None
print(grip.range)                 # (0.0, 2.11)
```

필요한 명령 하나씩 실행합니다. `grip.move(1.0, kp=8.0, kd=0.3)`으로 게인을 지정할 수 있습니다.

## 6. MIT 명령

```python
arm.move_mit(1, position=0.0, velocity=0.0,
             kp=0.0, kd=0.3, torque_feedforward=0.0)
```

결과: 1축 damping만 적용. 생략한 게인은 제품 기본값입니다.
명령은 supervisor가 계속 전송하며 다른 모터는 HOLD합니다.
`hold_mode`·`float_mode`·`move_j`·`move_p`로 전환하거나 종료하기 전까지 유지됩니다.

## 7. 정지·복구

| 함수 | 동작 |
| --- | --- |
| `arm.shutdown()` | 정상 종료: damping 및 연결 정리 |
| `arm.electronic_emergency_stop()` | 전자식 정지: damping, fault |
| `arm.disable()` | Enabled/Running에서 토크 차단. 팔 낙하 주의 |
| `arm.recover()` | 원인 해소 후 Idle로 복구. enable은 별도 |
| `arm.disconnect()` | 연결만 해제. 무구동 조회 프로그램용 |

종료는 `finally`에서 `shutdown()`을 호출하세요. damping은 기계식 브레이크가 아니며 팔이 내려올 수 있습니다.
shutdown 후 disable하려면 새 Arm 연결 → 모델 설정 → enable → disable 순서가 필요합니다.
enable 시 잠시 HOLD 힘이 들어가므로 팔을 지지하세요.
상태 전환 결과는 `.ok`, `.message`로 확인합니다. fault 원인은 `arm.manager.fault_reason()`입니다.

## 8. 기본 제어·안전 설정

| 항목 | 기본값 |
| --- | --- |
| supervisor / CAN 송신 | 100 Hz |
| 명령 갱신 timeout | 100 ms |
| 피드백 timeout | 250 ms |
| 실측 안전 범위 | 명령 범위 양끝에 0.15 rad 여유 (1.0.5부터) |
| 온도 warning / fault | 70 / 90 °C |

`create_arm()` → `enable()`이 제어루프를 시작합니다. 루프를 직접 시작할 필요는 없습니다.
게인·속도 설정은 [프로파일](profiles/README.md)을 사용하세요.

## 9. 교시장치 SDK와 teleop

`motomind-teaching-sdk`는 Milly·ROS 의존성이 없는 별도 wheel입니다.
교시장치 위치는 `TeachingDevice.read_positions()`로 읽으며 단위는 rad, 순서는 1~6축, 그리퍼입니다.
SDK의 고정 변환과 관절별 범위를 적용합니다. 범위 밖 위치는 최솟값/최댓값으로 제한하며,
읽기 실패 시 예외를 내고 이전 위치를 다시 반환하지 않습니다.

```python
from motomind_teaching import TeachingDevice

with TeachingDevice.from_profile('/dev/ttyACM0', 'examples/python/configs/teleoperation_tool_setting_example.json') as device:
    print(device.read_positions())  # 위치 읽기만 하며 토크를 켜지 않음
```

JSON에서 수정할 수 있는 설정은 다음 세 가지뿐이며 각 배열은 1~6축, 그리퍼 순서입니다.

- `torque_enable`: 각 축의 토크 사용 여부 (`true` / `false`)
- `current_limit`: 각 축의 전류 상한 (정수, 0~800 mA)
- `p_gain`: 각 축의 위치 게인 (정수, 0~100)

장치 ID·모델·좌표 변환·위치 범위·힘 피드백 규칙은 SDK 내부에서 관리합니다.
출력값 제한은 DXL 자체의 물리적 이동을 막는 기능은 아닙니다.
토크·시작 보간·종료 처리는 [DXL-only / Milly teleop 예제](examples/python/README.md)를 사용하세요.
teleop 시작 보간은 실제 경과시간 3초를 기준으로 끝내고 이후 새 위치를 직접 추종합니다.
기본 목표 주기는 30 Hz이며 실행 로그에 실제 Hz와 DXL 처리 시간을 표시합니다.
직접 제어 코드를 작성할 때도 교시장치 읽기 예외를 받아 추종 로봇의 정지 함수를 호출해야 합니다.
