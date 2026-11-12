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

중력보상은 기본 `False`(OFF)입니다. `move_j`/`move_p` 예제의 호출 인자를 `True`로
바꾸면 팔 6축 전체에 적용합니다. MIT·teleop 예제는 `--gravity-compensation` 옵션을
사용하면 팔 6축만 켜고 그리퍼는 OFF로 유지합니다. 실시간 루프에서 ON/OFF를 번갈아 사용하지 마세요.

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
1.0.6부터 shutdown은 Fault 후에도 약 10초 동안 `kd`를 0으로 낮춘 뒤 CAN을 정리합니다. 완료될 때까지 팔을 지지하거나 거치하세요. Fault/전자식 정지 자체는 shutdown 전까지 damping latch를 유지합니다.
`--help`: 추가 옵션.
검색 외 예제는 실제 모터를 enable합니다. 충돌 검사는 없으며 종료 damping은 자세 고정이 아닙니다.
무구동 표시는 [ROS description](../../SDK_ROS2_guide.md)을 사용하세요.

## 교시장치 — 두 예제

교시장치 SDK는 Milly와 독립된 선택 패키지입니다. 교시장치만 쓸 때는 아래 wheel만 설치합니다.
Milly teleop은 [Milly 설치](../../INSTALL.md) 후 teaching wheel을 추가로 설치하세요.

```bash
python -m pip install dist/teaching/*.whl
```

먼저 교시장치를 연결하고 포트 이름을 확인합니다. SDK 설치 없이도 확인할 수 있습니다.

```bash
ls /dev/tty* | grep -E '/dev/tty(USB|ACM)[0-9]+$'
```

납품 교시장치의 기본 포트는 `/dev/ttyACM0`입니다. 연결 순서나 종류에 따라 다른 번호의 ttyACM 또는 ttyUSB 포트로 표시될 수 있습니다.
**아래 명령의 `/dev/ttyACM0`은 확인된 포트 이름으로 바꾸세요.**
여러 포트가 보이면 교시장치 USB 연결 전후의 목록을 비교합니다.

최초 USB 권한 설정:

```bash
sudo usermod -aG dialout "$USER"
# 로그아웃/로그인하고 터미널·VS Code를 다시 실행
id -nG                      # 현재 터미널의 그룹에 dialout이 있는지 확인
ls -l /dev/ttyACM0           # 장치 그룹과 읽기/쓰기 권한 확인
teaching-check-port --port /dev/ttyACM0
```

`teaching-check-port`는 포트를 열지 않고 권한만 확인합니다.
재로그인 후에도 실패하면 `id`, `id "$USER"`, `ls -l /dev/ttyACM0` 결과를 확인하세요.
계정에 등록된 그룹과 현재 터미널에 적용된 그룹이 다를 수 있습니다.

로그아웃 없이 현재 연결된 장치를 바로 사용하려면 임시로 권한을 설정하세요.

```bash
sudo chmod 777 /dev/ttyACM0
teaching-check-port --port /dev/ttyACM0
```

이 임시 권한은 USB 재연결 시 초기화될 수 있습니다. `dialout` 설정은 다음 로그인부터 적용됩니다.

**ttyUSB 교시장치를 별도로 사용하는 경우의 필수 USB 지연 설정:** FTDI 어댑터는 예제 실행 전에 `latency_timer`를 **1 ms**로 설정하세요.
**납품용 `/dev/ttyACM0` 교시장치는 아래 FTDI 지연 설정을 건너뜁니다.**
각 Linux PC에서 아래 순서로 설정하고 확인하세요.

1. 교시장치 프로그램을 종료하고 스크립트를 최초 한 번 실행합니다. 설치 시 sudo 비밀번호를 요청합니다.

```bash
bash scripts/setup_teaching_usb.sh --port /dev/ttyUSB0
```

2. **교시장치 USB 케이블을 분리한 뒤 다시 연결합니다.** 새 규칙은 재연결 시 적용됩니다.
3. 재연결한 장치의 값을 확인합니다.

```bash
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
```

**출력이 `1`인 것을 확인한 뒤 예제를 실행하세요.** `16`이면 설정이 적용되지 않은 상태입니다.
`ttyUSB1`이면 확인 경로도 `/sys/bus/usb-serial/devices/ttyUSB1/latency_timer`로 바꿉니다.

예제의 기본 포트는 `/dev/ttyACM0`이며, 다른 포트는 `--port`로 지정합니다.
두 예제는 좌우 구분 없이 `configs/teleoperation_tool_setting_example.json`을 같은 폴더에서 읽습니다.
배열은 1~6축, 그리퍼 순서(ID 40~46)이며 사용자 설정은 세 항목입니다.

| JSON 항목 | 범위 |
| --- | --- |
| `torque_enable` | 각 축 `true` / `false` |
| `current_limit` | 정수 0~800 mA |
| `p_gain` | 정수 0~150 (팔 6축·그리퍼 공통, Teaching SDK 0.1.3부터) |

기본 설정은 3·4축과 그리퍼만 토크 ON합니다.
기본 P gain은 `[0, 0, 30, 40, 0, 0, 150]`이며 상한 변경으로 기본값이 높아지지는 않습니다.
팔 축의 출력 범위 초과 시 기존 5배 복원 게인을 적용하므로, 설정값 150에서는 750이 전송됩니다.
`--profile my_teaching.json`으로 수정한 JSON을 지정할 수 있습니다.

```bash
# 1. DXL만: Enter → 선택 축 토크 ON 및 3초 ramp → 위치 출력 → Ctrl+C로 OFF
python examples/python/dxl_only.py --port /dev/ttyACM0

# 2. DXL 토크 ON → Enter → Milly HOLD → 3초 보간 → teleop → Ctrl+C shutdown
python examples/python/milly_teleop.py --product-id MILLY_ABCD --port /dev/ttyACM0

# 중력보상 ON: 팔 1~6축만 적용, 그리퍼 OFF
python examples/python/milly_teleop.py --product-id MILLY_ABCD --port /dev/ttyACM0 --gravity-compensation
```

위치 변환과 관절별 출력 범위는 SDK 내부에서 관리하며 JSON에서 수정하지 않습니다.
Milly는 Python SDK `move_mit()`로 제어합니다. 팔 6축 KP는 `[30,30,30,15,15,5]`,
KD는 `[1.5,1.5,1.5,1.0,1.0,0.5]`, 그리퍼 KP/KD는 `5.0/0.5`입니다.
이는 교시장치 JSON의 `p_gain`과 별개입니다. `motion.max_vel: 0.5`는 계획 이동용이며
MIT teleop의 속도 제한으로 적용되지 않습니다.

추종성을 높이려면 아래 KP/KD를 추천합니다. 반응성도 좋아지므로 주의가 필요합니다.
배열 순서는 **1~6축, 그리퍼**이며 `milly_teleop.py`의 `KP`, `KD`에 적용합니다.
코드 기본값은 위 설정을 유지합니다.

```python
KP = [80, 80, 80, 20, 20, 5,   2]
KD = [ 6,  6,  6,  2,  2, 0.5, 0.2]
```

추종 기본 주기는 30 Hz이며 `--rate-hz 30`으로 지정할 수 있습니다.
시작 보간은 실제 경과시간 3초 기준으로 수렴하고 이후 새 위치를 직접 추종합니다.
통신·OS 지연이 있으면 3초 이후 첫 정상 샘플에서 추종으로 전환합니다.
실행 중 `Teleop: ... Hz; DXL step ... ms`로 실제 주기와 DXL 처리 시간을 확인하세요.
시작 전에 두 장치를 비슷한 자세로 맞추고 지지하세요. 보간에는 충돌 검사가 없습니다.
시작 실측 위치는 SDK 안전 범위 안에서 확인하고 명령 범위 경계로 맞춥니다.
안전 범위 밖이거나 피드백이 누락되면 이동을 시작하지 않습니다.
Enter 대기 중에도 DXL을 계속 읽으며, 통신 실패는 시작 취소 또는 Milly shutdown으로 이어집니다.
종료 시 Milly는 damping, 이 예제가 켠 DXL 축은 OFF합니다. 케이블 단절 시 DXL OFF 전송은 보장할 수 없습니다.

## 그리퍼 USB 카메라 — 실시간 영상

카메라 USB를 PC에 연결한 뒤 실행합니다. Ubuntu/Linux 데스크톱용이며 로봇·CAN·ROS 연결 없이
카메라만 사용할 수 있습니다. 로봇 제어 예제와 함께 실행할 수도 있습니다.

```bash
python -m pip install 'opencv-python>=4.8,<5'
python examples/python/camera_preview.py --list  # 장치 정보만 조회, OpenCV 설치 전에도 가능
python examples/python/camera_preview.py         # 목록에서 번호 선택 → 영상 창
```

**납품 카메라는 제조사 `HBVCAM Camera`, 모델 `USB Camera`, USB ID `0bdc:8088`인 항목을 선택하세요.**
일치하는 항목에는 **`Milly 그리퍼 카메라 후보`**를 표시합니다. 이름이 `USB Camera`인 것만으로
선택하지 말고 제조사·USB ID도 확인하세요. 현재 확인한 납품 모델 기준이며, 공급 모델 변경 시
실제 장치 정보를 다시 확인해야 합니다. 카메라와 로봇 제품 ID의 자동 연결은 지원하지 않습니다.

목록 예시 (번호·시리얼은 PC/카메라마다 다릅니다):

```text
[1] ASUS FHD webcam: ASUS FHD webca
    제조사: Kingcome | 모델: ASUS FHD webcam
[3] USB Camera: USB Camera [Milly 그리퍼 카메라 후보 — 납품 모델 USB 정보 일치]
    장치: /dev/video4 | USB: 0bdc:8088
    제조사: HBVCAM Camera | 모델: USB Camera | 시리얼: HB202400001
    by-path (권장): /dev/v4l/by-path/pci-0000:80:14.0-usb-0:9:1.0-video-index0
```

이 예에서는 `[3]`을 선택합니다. `ASUS FHD webcam`과 `ASUS IR camera`는 노트북 카메라입니다.
영상 포트만 표시하며 메타데이터 전용 포트는 제외합니다. 한 대만 있어도 자동 선택하지 않습니다.
번호는 현재 목록에만 유효하며, `/dev/video0`·`/dev/video4` 번호도 USB 연결 순서에 따라 바뀔 수 있습니다.

**확인한 납품 카메라 두 대는 이름·USB ID뿐 아니라 시리얼 `HB202400001`까지 같았습니다.**
이 경우 `/dev/v4l/by-id/usb-HBVCAM_Camera_USB_Camera_HB202400001-video-index0` 경로 하나가
어느 카메라를 가리키는지 연결 순서에 따라 바뀔 수 있습니다. 두 대를 연결하면 시리얼 중복을
표시하고 `--device`에 중복된 `by-id`를 지정하는 실행은 거부합니다.

처음 영상으로 그리퍼 카메라인지 확인한 뒤, 출력된 `다음 실행:` 명령을 복사해 재사용하세요.
기본 재실행 경로는 **물리 USB 포트를 기준으로 하는 `by-path`**입니다.
목록에서 확인한 실제 경로를 지정하면 해당 USB 포트의 카메라를 바로 열 수 있습니다:

```bash
# 아래 전체 경로를 자신의 --list 출력으로 바꾸세요.
python examples/python/camera_preview.py \
  --device /dev/v4l/by-path/pci-0000:80:14.0-usb-0:9:1.0-video-index0
```

`by-path`는 카메라 개체가 아닌 USB 포트를 구분합니다. 각 카메라를 한 대씩 연결해 영상을 확인한 뒤
좌우 USB 포트를 표시해 두세요. 같은 포트에 연결하면 재연결로 `/dev/videoN` 번호가 바뀌어도
그 USB 포트 경로를 재사용할 수 있습니다. 카메라를 서로 바꾸거나 허브·포트를 옮기면 영상을 다시 확인합니다.
`by-path`가 없는 장치는 현재 `/dev/videoN`을 사용하므로 재연결 후 다시 선택하세요.
다른 모델에서 고유한 시리얼이 제공된다면 `by-id`도 직접 지정할 수 있습니다.
지정한 장치가 없거나 열리지 않으면 오류로 종료합니다.

종료: 영상 창에서 `q` / `Esc`, 창 닫기 또는 터미널 `Ctrl+C`. 선택 단계에서는 `q`.
기본 요청은 MJPG 1280×720 / 30 FPS이며 실제 영상 크기와 드라이버 FPS를 출력합니다.
`--width 640 --height 480 --fps 30`으로 요청 값을 바꾸거나 `--duration 10`으로 자동 종료할 수 있습니다.

문제가 있으면:

- 목록에 없음: USB 연결과 `ls -l /dev/video*`를 확인합니다. `Permission denied`이면 장치 접근 권한을 확인합니다.
  Ubuntu에서 `video` 그룹 권한이 필요한 경우 `sudo usermod -aG video "$USER"` 후 로그아웃·로그인합니다.
- 열기/영상 수신 실패: 카메라를 사용하는 브라우저·영상회의 앱·다른 preview를 닫고 USB 연결을 확인합니다.
- 창이 안 열림: 데스크톱 터미널에서 실행하고 GUI 지원 `opencv-python`을 사용합니다.
  `opencv-python-headless`와 함께 설치하지 마세요. GUI 없는 SSH 세션에서는 `--list`만 사용할 수 있습니다.
- 실행 중 USB 분리: 수신 실패 후 종료합니다. 드라이버 수신 대기 때문에 오류 표시가 지연될 수 있습니다.
