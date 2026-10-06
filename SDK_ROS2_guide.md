# ROS2 가이드

Ubuntu 22.04 / x86_64 / Humble / Python 3.10 지원. Jazzy는 지원 예정입니다.
명령은 **release 루트** 기준입니다. `MILLY_ABCD`를 실제 제품 ID로 바꾸세요.
같은 로봇에는 제어 프로그램 하나만 실행하세요. move_j·move_p·MIT는 충돌 검사를 하지 않습니다.

## 1. 설치·시작

처음 설치하거나 같은 버전을 다시 설치할 때:

```bash
bash scripts/setup_ros_humble.sh
```

결과: SDK 설치 → ROS 빌드 → 설치 검사. [CAN 설정](INSTALL.md#can-연결)

터미널 A — 드라이버:

```bash
source scripts/ros_env.sh
ros2 launch milly_sdk_bringup bringup.launch.py product_id:=MILLY_ABCD
```

결과: `Idle`, 모터 GUI 표시. 자동 enable은 하지 않습니다. GUI를 닫아도 제어는 유지됩니다.

터미널 B — 새 터미널마다 실행:

```bash
source scripts/ros_env.sh
ros2 service call /milly/MILLY_ABCD/enable std_srvs/srv/Trigger '{}'
```

결과: `success: true`, `Running`. 현재 자세에서 HOLD를 시작합니다.

### Bringup 인자

| 인자 | 기본값 | 허용값 / 의미 |
| --- | --- | --- |
| `product_id` | 필수 | 각인된 `MILLY_<ID>` |
| `motor_gui` | `true` | `true` / `false`, 버튼 없는 모터 조회 창 |
| `gui` | `false` | `true` / `false`, RViz도 함께 실행 |
| `supervisor_rate_hz` | `100.0` | 20~100 Hz; 현재 배포의 CAN 주기는 100 Hz |
| `publish_rate_hz` | `30.0` | 1~100 Hz; ROS 피드백 발행 주기 |
| `feedback_stale_s` | `0.5` | 유한한 양수(s); ROS 표시의 stale 판정 기준 |

시작 시 지정하며 실행 중 `ros2 param set`으로 변경하지 않습니다.
`feedback_stale_s`는 SDK의 통신 안전 timeout을 변경하지 않습니다.

```bash
# 위 드라이버 대신 실행: 모터 GUI OFF, RViz ON
ros2 launch milly_sdk_bringup bringup.launch.py product_id:=MILLY_ABCD motor_gui:=false gui:=true
ros2 param get /milly/MILLY_ABCD/milly_driver publish_rate_hz
```

기본 설정의 조회 결과는 `Double value is: 30.0`입니다. 드라이버가 실행 중이어야 합니다.

## 2. 요청 형식

[관절·게인·속도·토크 범위와 적용 조건](milly_description/README.md)은 Python SDK와 공통입니다.

| 요청 | 형식 |
| --- | --- |
| `move_j.positions` | 1→6축 순서의 rad 6개; 그리퍼 제외 |
| `move_p.pose` | `[x,y,z,roll,pitch,yaw]`, m/rad |
| 선택 scalar | `[]`=기본값, `[값]`=단일 값; 2개 이상은 거부 |
| `set_gains` | Idle에서 arm은 kp/kd 각각 6개, gripper는 각각 1개; 다음 enable에 적용 |

현재 게인·범위는 `get_robot_info`로 확인하세요. `move_j`·`move_p` 요청의 kp/kd는 현재 적용되지 않습니다.

```bash
ros2 service call /milly/MILLY_ABCD/get_robot_info milly_sdk_interfaces/srv/GetRobotInfo '{}'

# enable 전 Idle에서 실행: 다음 enable부터 적용
ros2 service call /milly/MILLY_ABCD/set_gains milly_sdk_interfaces/srv/SetGains '{group: arm, kp: [30.0, 30.0, 30.0, 15.0, 15.0, 5.0], kd: [1.5, 1.5, 1.5, 1.0, 1.0, 0.5]}'
```

## 3. Topic — 피드백

```bash
ros2 topic echo /milly/MILLY_ABCD/status --once
ros2 topic echo /milly/MILLY_ABCD/motor_states --once --qos-reliability best_effort
ros2 topic echo /milly/MILLY_ABCD/joint_states --once --qos-reliability best_effort
ros2 topic echo /milly/MILLY_ABCD/flange_pose --once --qos-reliability best_effort
ros2 topic hz /milly/MILLY_ABCD/motor_states
```

| 토픽 | 타입 | 기대 결과 |
| --- | --- | --- |
| `status` | `milly_sdk_interfaces/msg/DriverStatus` | 정상 수신 시 `feedback_valid: true`; 상태·fault·`last_error` |
| `motor_states` | `milly_sdk_interfaces/msg/MotorStates` | 1~7번 위치·속도·토크·온도·수신 경과시간 |
| `joint_states` | `sensor_msgs/msg/JointState` | fresh한 팔 6축 실측값 |
| `display_joint_states` | `sensor_msgs/msg/JointState` | RViz용 팔 위치 + 추정 finger 위치 |
| `flange_pose` | `geometry_msgs/msg/PoseStamped` | base 기준 flange 위치(m)·quaternion |

기본 발행 30 Hz, 제어 100 Hz. `--once`를 빼면 계속 수신합니다. 구독 종료는 로봇 정지가 아닙니다.

## 4. Service — 명령별 실행

경로: `/milly/<제품 ID>/<서비스 이름>`. 응답 공통: `success`, `message`.
`[]`는 기본값, `[값]`은 선택 scalar입니다. pose 순서는 `[x,y,z,roll,pitch,yaw]` (m/rad)입니다.

| 서비스 | 타입 | 요청 → 결과 | 예제 명령어 (`MILLY_ABCD`) |
| --- | --- | --- | --- |
| `enable` | `std_srvs/srv/Trigger` | `{}` → 현재 자세 제어 시작 | `ros2 service call /milly/MILLY_ABCD/enable std_srvs/srv/Trigger '{}'` |
| `shutdown` | `std_srvs/srv/Trigger` | `{}` → damping·연결 종료 | `ros2 service call /milly/MILLY_ABCD/shutdown std_srvs/srv/Trigger '{}'` |
| `emergency_stop` | `std_srvs/srv/Trigger` | `{}` → 전자식 정지·명령 차단 | `ros2 service call /milly/MILLY_ABCD/emergency_stop std_srvs/srv/Trigger '{}'` |
| `disable` | `std_srvs/srv/Trigger` | `{}` → Enabled/Running에서 토크 차단. shutdown 후에는 드라이버 재시작·enable 필요 | `ros2 service call /milly/MILLY_ABCD/disable std_srvs/srv/Trigger '{}'` |
| `recover` | `std_srvs/srv/Trigger` | `{}` → 원인 해소 후 복구. enable은 별도 | `ros2 service call /milly/MILLY_ABCD/recover std_srvs/srv/Trigger '{}'` |
| `hold_mode` | `std_srvs/srv/Trigger` | `{}` → 현재 자세 HOLD | `ros2 service call /milly/MILLY_ABCD/hold_mode std_srvs/srv/Trigger '{}'` |
| `move_j` | `MoveJ` | `positions`: 6개 rad, `max_vel`: 선택 rad/s → `duration_s` | `ros2 service call /milly/MILLY_ABCD/move_j milly_sdk_interfaces/srv/MoveJ '{positions: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0], max_vel: [0.2]}'` |
| `move_p` | `MoveP` | `pose`: 6개 m/rad, `max_vel`: 선택 rad/s → `duration_s` | `ros2 service call /milly/MILLY_ABCD/move_p milly_sdk_interfaces/srv/MoveP '{pose: [0.000052, -0.109343, 0.238285, 1.570796, 0.0, 0.0], max_vel: [0.2]}'` |
| `gripper` | `Gripper` | `operation`: open/close/move, `position`: rad, `kp/kd`: 선택 → `target` rad | `ros2 service call /milly/MILLY_ABCD/gripper milly_sdk_interfaces/srv/Gripper '{operation: open}'` |
| `float_mode` | `FloatMode` | `{}` → FLOAT ON. OFF는 shutdown | `ros2 service call /milly/MILLY_ABCD/float_mode milly_sdk_interfaces/srv/FloatMode '{}'` |
| `fk` | `Fk` | `joints`: 6개 rad 또는 `[]`(현재값) → `pose` | `ros2 service call /milly/MILLY_ABCD/fk milly_sdk_interfaces/srv/Fk '{joints: []}'` |
| `get_robot_info` | `GetRobotInfo` | `{}` → ID·버전·한계·기본 게인·주기 | `ros2 service call /milly/MILLY_ABCD/get_robot_info milly_sdk_interfaces/srv/GetRobotInfo '{}'` |
| `set_max_vel` | `SetMaxVel` | `max_vel`: `(0, 2.0]` rad/s → 기본 속도 | `ros2 service call /milly/MILLY_ABCD/set_max_vel milly_sdk_interfaces/srv/SetMaxVel '{max_vel: 0.2}'` |
| `set_gains` | `SetGains` | Idle에서 `group`: arm/gripper, `kp/kd`: 각각 6개/1개 → 다음 enable에 적용 | `ros2 service call /milly/MILLY_ABCD/set_gains milly_sdk_interfaces/srv/SetGains '{group: gripper, kp: [5.0], kd: [0.5]}'` |

명령은 필요한 항목만 하나씩 실행하세요. `move_j`·`move_p`는 팔 6축 zero 자세를 목표로 하므로 이동 경로를 먼저 확인하세요.

타입을 생략한 namespace는 `milly_sdk_interfaces/srv/`입니다. 정확한 필드는 다음처럼 확인합니다.

```bash
ros2 interface show milly_sdk_interfaces/srv/SetGains
ros2 interface show milly_sdk_interfaces/msg/MitCommand
```

move_j·move_p의 `success: true`는 궤적 전송 완료입니다. 실측 도달은 피드백으로 확인하세요.
move_p는 IK 후 관절 PTP 이동이며 직선 이동이 아닙니다. IK 실패 시 `success: false`입니다.

```bash
# 그리퍼: 필요한 명령 하나만 실행
ros2 service call /milly/MILLY_ABCD/gripper milly_sdk_interfaces/srv/Gripper '{operation: close}'
ros2 service call /milly/MILLY_ABCD/gripper milly_sdk_interfaces/srv/Gripper '{operation: move, position: 1.0, kp: [5.0], kd: [0.5]}'
```

결과: `target`은 각각 0.0, 1.0 rad. 실제 도달 확인은 `motor_states`에서 합니다.

## 5. Topic — MIT 명령

Running에서 1축 damping만 지정하는 예입니다. 전체 팔 중력보상이 아닙니다.

```bash
ros2 topic pub --once /milly/MILLY_ABCD/move_mit milly_sdk_interfaces/msg/MitCommand '{motor_id: 1, position: 0.0, velocity: 0.0, torque_feedforward: 0.0, kp: [0.0], kd: [0.3]}'
ros2 topic echo /milly/MILLY_ABCD/status --once
```

성공 응답은 없으며 `status.last_error`와 드라이버 로그를 확인합니다.
발행 종료 후에도 마지막 명령이 유지됩니다. 시험 후 shutdown하세요.

## 6. 중력보상·종료

enable 후 팔을 지지하고 ON을 실행하세요.

```bash
# ON
ros2 service call /milly/MILLY_ABCD/float_mode milly_sdk_interfaces/srv/FloatMode '{}'

# OFF / 정상 종료
ros2 service call /milly/MILLY_ABCD/shutdown std_srvs/srv/Trigger '{}'
```

결과: ON은 FLOAT, OFF는 shutdown/damping. FLOAT 중 1축·그리퍼는 `kp=kd=t_ff=0`입니다.
shutdown 후 터미널 A에서 Ctrl+C로 드라이버를 종료하세요. **터미널 A의 Ctrl+C만으로도 shutdown합니다.**
명령을 보내는 터미널 B의 Ctrl+C나 timeout은 이동 취소가 아닙니다. damping은 기계식 고정이 아닙니다.

힘을 완전히 풀려면 **팔을 지지하고**, Running 상태에서 disable하세요.

```bash
ros2 service call /milly/MILLY_ABCD/disable std_srvs/srv/Trigger '{}'
```

결과: 토크 OFF, `Idle`. 이미 shutdown했다면 드라이버 재시작 → enable 성공 확인 → disable 순서입니다.
재시작 직후 Idle의 disable은 OFF 명령을 보내지 않습니다. enable 시에는 현재 자세 HOLD로 잠시 힘이 들어갑니다.

## 7. RViz·무구동 확인

드라이버 실행 중 별도 터미널 — 피드백 구독만 하며 CAN에 추가 연결하지 않습니다:

```bash
source scripts/ros_env.sh
ros2 launch milly_sdk_description display.launch.py product_id:=MILLY_ABCD
```

결과: 로봇 자세 표시. 창을 닫아도 드라이버는 유지됩니다. bringup의 `gui:=true`와 중복 실행하지 마세요.

무구동 확인 — **다른 제어 프로그램을 종료하고 토크가 꺼진 팔을 지지한 뒤** 실행:

```bash
ros2 launch milly_sdk_description description_check.launch.py product_id:=MILLY_ABCD rviz_gui:=true motor_gui:=true
```

결과: RViz·raw 위치 GUI, 손으로 움직인 관절이 함께 변합니다. Ctrl+C는 연결만 해제합니다.

```bash
# 두 번째 터미널
source scripts/ros_env.sh
ros2 topic echo /milly/MILLY_ABCD/description_check/description_status
```

정상 수신 시 `feedback_valid: true`, missing/stale 목록은 비어 있습니다.
그리퍼 표시: raw 0 / 1.055 / 2.11 rad → 각 finger 0.05 / 0.025 / 0 m.
finger는 선형 추정값이며 stale이면 갱신하지 않습니다. raw 값은 `motor_states`에서 확인하세요.

## 8. 인터페이스·재빌드

```bash
ros2 service list -t
ros2 topic list -t
ros2 interface show milly_sdk_interfaces/srv/MoveJ
ros2 interface show milly_sdk_interfaces/msg/MitCommand
ros2 action list -t
```

ROS 소스 수정 후에는 드라이버를 종료하고 빌드합니다:

```bash
source scripts/ros_env.sh
python -m colcon build --base-paths ros/src --cmake-args \
  -DPython3_EXECUTABLE="$VIRTUAL_ENV/bin/python" -DPYTHON_EXECUTABLE="$VIRTUAL_ENV/bin/python"
source scripts/ros_env.sh
```

| 증상 | 확인 |
| --- | --- |
| `ros2` / 패키지를 찾지 못함 | 새 터미널에서 `source scripts/ros_env.sh` |
| SDK import / ROS 타입 오류 | 드라이버 종료 후 `bash scripts/setup_ros_humble.sh` |
| 로봇 검색 실패 | 전원·CAN·bitrate·제품 ID |
| MISSING / STALE | status의 수신 경과시간 |
| RViz transform 오류 | Fixed Frame=`제품ID/base_link`, TF Prefix=`제품ID` |
