# Python SDK — 함수별 사용법

[설치](INSTALL.md) · [전체 예제 명령](examples/python/README.md) · [제품별 설정](profiles/README.md) · [관절·게인·명령 범위](milly_description/README.md)
각도 rad, 속도 rad/s, 토크 N·m. pose는 base 기준 flange `[x,y,z,roll,pitch,yaw]` (m/rad)입니다.
같은 로봇에는 제어 프로그램 하나만 실행하세요. 이동 API에는 충돌 검사가 없습니다.

## 1. 연결 → enable → 이동 → 종료

아래 코드를 `move_zero.py`로 저장하고 `MILLY_ABCD`를 실제 제품 ID로 바꾸세요.

```python
import motomind_milly as mm
from motomind_robot_model import RobotModel

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
| `arm.shutdown()` | Fault 후에도 10초 동안 damping kd → 0 후 연결 정리 |
| `arm.electronic_emergency_stop()` | 전자식 정지: damping, fault |
| `arm.disable()` | Enabled/Running에서 토크 차단. 팔 낙하 주의 |
| `arm.recover()` | 원인 해소 후 Idle로 복구. enable은 별도 |
| `arm.disconnect()` | 연결만 해제. 무구동 조회 프로그램용 |

종료는 `finally`에서 `shutdown()`을 호출하세요. 1.0.6부터 Fault/전자식 정지 후에도 관절별 `kd`를
10초 동안 선형으로 0까지 낮추고 최종 0 명령을 반복 전송한 뒤 CAN을 정리합니다.
`kp`, 속도 목표, feedforward 토크는 0으로 유지합니다. 호출이 반환할 때까지 팔을 지지하거나 거치하세요.
`kd=0`은 모터 disable과 다르며 중력·외력으로 팔이 움직일 수 있습니다.
Fault/전자식 정지 자체는 damping latch를 유지하며, 이후 `shutdown()`에서 감쇠를 해제합니다.
감쇠 도중 새 Fault가 발생하면 해제를 중단합니다. shutdown 상태에서 enable/disable은 허용되지 않습니다.
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

### 자동 로그 저장 — 1.1.0부터

SDK는 정상 운영 INFO·경고·오류와 SDK API 예외를 자동으로 `logs/`에 저장합니다.
release 루트 또는 그 하위에서 실행하면 `<release>/logs/`를 사용합니다.
그 외 설치 위치에서는 실행 디렉터리와 SDK 설치 위치에서 release를 찾고, 찾지 못하면 현재 디렉터리의 `logs/`를 사용합니다.
파일 이름은 `2026-10-31_153000_123456_1234_ab12cd34_0000.txt`처럼 날짜·실행 식별자를 포함합니다.
프로그램 재실행·동시 실행은 파일을 분리하고, 자정이나 파일당 10MB에 도달하면 새 파일을 만듭니다.
디렉터리 전체 200MB 한도에서 오래된 닫힌 로그부터 정리합니다. 실행 중인 파일은 삭제하지 않습니다.

INFO·WARNING·ERROR는 별도 설정 없이 콘솔과 파일에 자동 출력됩니다.
`mm.enable_logging()`은 deprecated이며 새 코드에서는 호출하지 마세요.
기존 호출과 `level` 인자는 호환성을 위해 유지하며, 호출 시 `DeprecationWarning`으로 안내합니다.
필터 없는 표준 콘솔 `StreamHandler`가 이미 처리하는 메시지는 중복 출력하지 않습니다.
파일에는 날짜·시간대·밀리초·세션·로봇 ID·CAN·설정 경로/해시·적용 게인·이동 결과·모터별 오류 문맥이 남습니다.
SDK 밖에서 출력한 임의의 `print()`를 수집하는 기능은 아닙니다. 원인 전달 시 같은 실행의 로그 파일들을 함께 보내주세요.

```python
print(mm.logging_status())  # 저장 위치, 기록/누락/실패 횟수, 최근 저장 오류
mm.flush_logs(timeout=1.0)  # 필요 시 제한 시간 내 기록 대기. 로봇 상태를 변경하지 않음
```

저장 경로는 실행 전에 `MOTOMIND_MILLY_LOG_DIR` 환경 변수로 변경할 수 있습니다.
저장 실패는 매번 `LOG_SAVE_FAILED`로 알리며 로봇 제어로 예외를 전파하거나 자동 shutdown하지 않습니다.
모든 파일이 실행 중이어서 공간을 확보하지 못하면 저장 실패로 안내합니다.
기록은 프로세스당 백그라운드 스레드 하나가 처리하고 정상 프로그램 종료 시 최대 1초 대기합니다.
강제 종료·정전·저장 장치 장애에서는 일부 기록이 유실될 수 있습니다.

enable 실패 진단은 추가 CAN 요청 없이 캐시에서 모터 ID·관절명·fault 비트·온도·수신 age·mode를 출력합니다.
미수신 값은 `null`, 오래된 값은 age/fresh로 구분합니다. 최초 원인을 보존하며 실제 실패 순간의 응답과 캐시 시점은 다를 수 있습니다.
온도 경고는 발생·해소를 표시하고 반복 경고는 요약합니다. 코어 명령 조정·거부는 최신 보고서를 주기적으로 확인하므로
짧은 개별 이벤트 모두를 보존하는 실시간 이벤트 기록기는 아닙니다.
이동 중 Fault/제어 중단은 예외와 `MOVE_ABORTED`로 안내합니다.
`MOVE_COMPLETED`는 명령 계획의 배포 완료이며 실측 위치 정밀도/정착을 보증하지 않습니다.

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
- `p_gain`: 각 축의 위치 게인 (정수, 팔 6축·그리퍼 모두 0~150, Teaching SDK 0.1.3부터)

장치 ID·모델·좌표 변환·위치 범위·힘 피드백 규칙은 SDK 내부에서 관리합니다.
출력값 제한은 DXL 자체의 물리적 이동을 막는 기능은 아닙니다.
토크·시작 보간·종료 처리는 [DXL-only / Milly teleop 예제](examples/python/README.md)를 사용하세요.
teleop 시작 보간은 실제 경과시간 3초를 기준으로 끝내고 이후 새 위치를 직접 추종합니다.
기본 목표 주기는 30 Hz이며 실행 로그에 실제 Hz와 DXL 처리 시간을 표시합니다.
직접 제어 코드를 작성할 때도 교시장치 읽기 예외를 받아 추종 로봇의 정지 함수를 호출해야 합니다.

## 10. 그리퍼 USB 카메라 영상

```bash
python -m pip install 'opencv-python>=4.8,<5'
python examples/python/camera_preview.py
```

목록에서 `HBVCAM Camera` / USB `0bdc:8088`인 **Milly 그리퍼 카메라 후보**를 선택합니다.
확인한 납품 카메라 두 대는 시리얼도 같으므로, 다음 실행부터 `--device`에 출력된 `by-path` 경로를 지정합니다.
처음 영상으로 확인한 뒤 같은 USB 포트를 사용하세요. 중복된 `by-id`로 개체를 구분하는 실행은 거부합니다.
`--list`는 OpenCV 없이 장치 정보만 조회합니다. Milly·Teaching SDK·CAN·ROS 연결은 필요하지 않습니다.
[카메라 선택 기준·동일 모델 여러 대·창 종료·문제 해결](examples/python/README.md#그리퍼-usb-카메라--실시간-영상)을 확인하세요.
