# Milly SDK 1.0.5

- 팔 6축과 그리퍼의 `safe_position` 최솟값을 각각 0.1 rad 낮추고, 최댓값을 각각 0.1 rad 높였습니다. 명령 범위 양끝의 실측 안전 여유는 0.05 rad에서 0.15 rad로 늘어납니다.
- 새 안전 범위를 벗어나면 기존처럼 fault와 damping latch가 동작합니다. `move_j()`의 계획 범위에도 확장된 `safe_position`이 적용되며, 직접 MIT 위치 명령 범위와 교시장치 출력 범위는 유지됩니다.
- README와 Python 가이드에 새 관절 범위를 안내합니다.
