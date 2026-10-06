uint8 id
string joint_name
float64 position
float64 velocity
float64 torque
float64 temperature
uint16 fault_bits
uint8 mode_status
bool received
bool fresh
# -1 means never received, otherwise seconds since the actual CAN feedback.
float64 feedback_age_s
