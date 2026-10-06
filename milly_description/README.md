# Milly 모델 및 제어 범위

Python SDK와 ROS2의 공통 기준입니다. [Python 사용법](../SDK_python_guide.md) · [ROS2 명령어](../SDK_ROS2_guide.md)

## 좌표·단위

| 항목 | 값 |
| --- | --- |
| 팔 | 1→6축 = `joint_1`~`joint_6`, motor raw rad |
| 속도 / 토크 | rad/s / N·m |
| FK·pose 기준 | `base_link` → `link_6` (flange), `[x,y,z,roll,pitch,yaw]` (m/rad) |
| 그리퍼 모터 7 | 닫힘 `0.0`, 열림 `2.11` rad |
| RViz finger | `0.05 * (1 - clamp(raw / 2.11, 0, 1))` m, 표시용 추정 |

## 관절·게인 범위

| 모터 | position (rad) | kp | kd | 기본 kp / kd |
| --- | --- | --- | --- | --- |
| 1 | -2.80 ~ 2.80 | 0 ~ 200 | 0 ~ 20 | 30 / 1.5 |
| 2 | -3.20 ~ 0.00 | 0 ~ 200 | 0 ~ 20 | 30 / 1.5 |
| 3 | -2.75 ~ 0.00 | 0 ~ 200 | 0 ~ 20 | 30 / 1.5 |
| 4 | -2.42 ~ 2.42 | 0 ~ 100 | 0 ~ 10 | 15 / 1.0 |
| 5 | -1.84 ~ 1.70 | 0 ~ 100 | 0 ~ 10 | 15 / 1.0 |
| 6 | -1.55 ~ 1.55 | 0 ~ 100 | 0 ~ 10 | 5 / 0.5 |
| 7 (gripper) | 0.00 ~ 2.11 | 0 ~ 50 | 0 ~ 5 | 5 / 0.5 |

기본 kp/kd는 HOLD·이동용이며 [제품 프로파일](../profiles/README.md)에 따라 달라질 수 있습니다.
ROS에서는 `get_robot_info`로 현재 설정을 확인합니다. FLOAT 값은 아래 별도 표를 따릅니다.

팔 URDF 범위는 위 position 범위와 같습니다. 실측 안전 범위(`safe_position`)는 모든 모터에서
`[position 최솟값 - 0.05, position 최댓값 + 0.05]` rad입니다. 이 여유는 명령 범위를 넓히지 않습니다.

## 공통 명령 범위·처리

| 입력 | 범위 / 처리 |
| --- | --- |
| 관절 목표 | 위 position 범위의 6개 rad; `move_j` 범위 밖 목표는 거부 |
| Cartesian 목표 | 도달 가능한 IK 해와 관절 범위 필요; `move_p`는 직선 이동이 아닌 관절 PTP |
| `max_vel` | `0 < 값 <= 2.0` rad/s; 출하 기본 0.5, 제품 프로파일로 변경 가능 |
| 그리퍼 목표 | 0~2.11 rad; 범위 밖 값은 이 범위로 제한 |
| MIT `motor_id` | 1~7 |
| MIT `position` / `kp` / `kd` | 위 모터별 범위 |
| MIT `velocity` | -20~20 rad/s |
| MIT `torque_feedforward` | -30~30 N·m |

MIT 위치·속도·토크·게인은 SDK 한계로 제한됩니다. 다른 안전 조건 위반 시 Fault가 발생할 수 있습니다.
위 속도·토크 한계와 URDF effort/velocity는 명령·모델 설정값이며 검증된 정격이나 권장 운용값이 아닙니다.

**현재 `move_j`·`move_p`의 호출별 kp/kd는 supervisor 경로에 적용되지 않습니다.**
이동 게인은 enable 전에 제품 프로파일(Python) 또는 Idle의 `set_gains`(ROS)로 설정하세요.

## 중력보상 기본값

| 항목 | 값 |
| --- | --- |
| FLOAT 1축·그리퍼 | `kp=0, kd=0, t_ff=0` |
| FLOAT 2~6축 kp | 모두 `0` |
| FLOAT 2~6축 kd | `[0.3, 0.3, 0.15, 0.15, 0.15]` |
| FLOAT 2~6축 보상 gain | `[1.0, 0.9, 1.0, 1.0, 1.0]` |

FLOAT는 ON/OFF만 제공하며 scale·게인 조정 인자는 없습니다.
기본 공장 중력 보정이 포함되어 있으며 모델·보정 파일의 해시가 일치해야 적용됩니다.

## 제어 중 RViz 표시

```bash
source scripts/ros_env.sh
ros2 launch milly_sdk_description display.launch.py product_id:=MILLY_ABCD
```

기존 드라이버의 피드백만 구독합니다. 창을 종료해도 제어는 계속됩니다.

## 무구동 관절 확인

release 루트에서 실행합니다. 토크가 꺼진 팔을 지지하세요.

```bash
source scripts/ros_env.sh
ros2 launch milly_sdk_description description_check.launch.py \
  product_id:=MILLY_ABCD rviz_gui:=true motor_gui:=true
```

결과: 손으로 움직인 관절이 RViz에 표시됩니다. enable하지 않으며 Ctrl+C는 연결만 해제합니다.
그리퍼 선형 표시는 실측 손가락 변위가 아닙니다.
