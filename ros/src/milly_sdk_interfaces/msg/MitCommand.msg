# One motor, SDK joint-space rad / rad/s / Nm. Empty gain arrays use profile defaults.
uint8 motor_id
float64 position
float64 velocity
float64 torque_feedforward
float64[] kp
float64[] kd
