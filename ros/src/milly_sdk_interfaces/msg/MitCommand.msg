# One motor, SDK joint-space rad / rad/s / Nm. Empty gain arrays use profile defaults.
uint8 motor_id
float64 position
float64 velocity
float64 torque_feedforward
float64[] kp
float64[] kd
# This arm motor only; user torque_feedforward is added to gravity FF.
bool gravity_compensation false
