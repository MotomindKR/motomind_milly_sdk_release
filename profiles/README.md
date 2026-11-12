# 제품별 설정

release 루트에서 `MILLY_ABCD`를 실제 제품 ID로 바꾸세요.

```bash
cp profiles/MILLY_SAMPLE.yaml profiles/MILLY_ABCD.yaml
export MOTOMIND_CONFIG_DIR="$PWD/profiles"
```

`MILLY_ABCD.yaml`에서 필요한 게인·속도만 변경하고 프로그램을 재시작합니다.
새 터미널에도 위 export가 필요합니다. ROS는 `source scripts/ros_env.sh`가 설정합니다.

- 생략한 값은 SDK 기본값을 사용합니다.
- 기본 motion 게인은 Joint 5에 `kp=20`, `kd=2.0`을 사용합니다. 제품별 프로파일에 명시한 게인이 있으면 그 값이 우선합니다.
- `MILLY_DEFAULT.yaml`은 참고 사본입니다. 이 파일을 수정해도 내장 기본값은 바뀌지 않습니다.
- motor ID·방향·관절 한계는 사용자 설정 대상이 아닙니다.

[함수별 사용법](../SDK_python_guide.md) · [기본 FLOAT 설정](../milly_description/README.md)
