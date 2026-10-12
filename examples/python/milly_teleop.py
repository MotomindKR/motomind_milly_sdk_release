#!/usr/bin/env python3
"""DXL enable -> Enter -> 3 s Milly interpolation -> teleop -> shutdown.

Uses one Milly SDK Arm/supervisor and the independent teaching SDK. No ROS.
Start with similar poses; interpolation does not provide collision checking.
"""
import math
import time

from _teaching import ignore_signals, parser, session, setup, wait_for_enter

# User-selected MIT follower gains: motion joint_1..6, then gripper.
# motion.max_vel is for planned moves; it is not a MIT teleop velocity limit.
KP = (30., 30., 30., 15., 15., 5., 5.)
KD = (1.5, 1.5, 1.5, 1., 1., .5, .5)
JOINTS = ('joint_1', 'joint_2', 'joint_3', 'joint_4', 'joint_5', 'joint_6', 'gripper')
HOLD_SECONDS = 1.5
WARMUP_SECONDS = 3.


def validate_follower(arm, profile):
    if arm._config is None:
        raise ValueError('Milly product configuration is required')
    motors = tuple(arm._config.motors)
    if tuple(m.joint_name for m in motors) != JOINTS or tuple(profile['joint_names']) != JOINTS:
        raise ValueError('Milly and teaching device must use joint_1..6, gripper order')
    if len(profile['position_limits_rad']) != len(motors):
        raise ValueError('teaching limits must match Milly joints')
    for motor, (lo, hi), kp, kd in zip(motors, profile['position_limits_rad'], KP, KD):
        limits = motor.limits
        if not limits.position_min <= lo <= hi <= limits.position_max:
            raise ValueError(f'{motor.joint_name}: teaching range exceeds Milly position limits')
        if not limits.kp_min <= kp <= limits.kp_max or not limits.kd_min <= kd <= limits.kd_max:
            raise ValueError(f'{motor.joint_name}: follower gains exceed Milly limits')
    return motors


def validate_positions(motors, values, *, feedback=False):
    values = tuple(values)
    if len(values) != len(motors):
        raise ValueError('incomplete Milly/teaching positions')
    for motor, value in zip(motors, values):
        lo, hi = (motor.safety.safe_position_min, motor.safety.safe_position_max) if feedback else (
            motor.limits.position_min, motor.limits.position_max)
        if (value is None or not math.isfinite(value)
                or not lo <= value <= hi):
            raise ValueError(f'{motor.joint_name}: missing or invalid position')
    if feedback:
        # CAN quantization can report zero just beyond a command boundary.
        # Match SDK HOLD: accept only existing safe feedback margins, then
        # keep every interpolation command inside limits.position.
        return tuple(min(max(value, motor.limits.position_min), motor.limits.position_max)
                     for motor, value in zip(motors, values))
    return values


def run_teleop(dev, controller, profile, arm_factory, *, rate_hz=30., duration=None,
               confirm=wait_for_enter, clock=time.monotonic, sleep=time.sleep):
    with session(dev):
        arm = None
        enable_attempted = False
        try:
            arm = arm_factory()
            motors = validate_follower(arm, profile)
            print('Torque axes:', controller.ids)
            print('Support the teaching device: enabling DXL torque with a 3 s ramp.', flush=True)
            controller.enable()
            print('Milly positions before enable (rad):', arm.get_joint_angles(), flush=True)
            confirm(controller, rate_hz)
            # Discard any pre-Enter sample. Never enable Milly after input has failed.
            validate_positions(motors, controller.step())
            enable_attempted = True
            result = arm.enable()
            if not result.ok:
                raise RuntimeError(f'Milly enable failed: {result.message}')
            settled = clock()
            while clock() - settled < HOLD_SECONDS:
                controller.step()
                if not arm.is_ok():
                    raise RuntimeError('Milly fault during HOLD')
                sleep(1 / rate_hz)
            start = validate_positions(motors, arm.get_joint_angles(), feedback=True)
            target = validate_positions(motors, controller.step())
            print('Milly start:', start, 'Teaching target:', target, flush=True)
            print('Interpolating for 3 s, then teleop. Ctrl+C -> shutdown.', flush=True)
            current = start
            started = clock()
            deadline = started + WARMUP_SECONDS
            last_update = started
            report_start, report_ticks = None, 0
            while duration is None or clock() - started < duration:
                tick = clock()
                target = validate_positions(motors, controller.step())
                sampled = clock()
                if not arm.is_ok():
                    raise RuntimeError('Milly fault; stopping teleop')
                # Legacy convergence rule, with remaining TIME instead of iterations.
                # At/after the deadline, the next fresh sample is followed directly.
                left = deadline - last_update
                fraction = min(1., max(0., (sampled - last_update) / left)) if left > 0 else 1.
                current = tuple(a + (b - a) * fraction for a, b in zip(current, target))
                last_update = sampled
                validate_positions(motors, current)  # entire sample before any motor update
                for motor, position, kp, kd in zip(motors, current, KP, KD):
                    if not arm.move_mit(motor.id, position=position, velocity=0., kp=kp, kd=kd):
                        raise RuntimeError(f'Milly rejected MIT target for {motor.joint_name}')
                if report_start is None:
                    report_start = sampled
                else:
                    report_ticks += 1
                if sampled - report_start >= 1.:
                    phase = 'following' if sampled >= deadline else 'interpolating'
                    print(f'Teleop: {report_ticks / (sampled - report_start):.1f} Hz '
                          f'(target {rate_hz:g}); DXL step {(sampled - tick) * 1000:.1f} ms; {phase}', flush=True)
                    report_start, report_ticks = sampled, 0
                delay = max(0., 1 / rate_hz - (clock() - tick))
                if clock() < deadline:
                    delay = min(delay, deadline - clock())
                sleep(max(0., delay))
        finally:
            with ignore_signals():
                if arm is not None:
                    if enable_attempted:
                        result = arm.shutdown()  # canonical damping; never arm.disable()
                        if not result.ok:
                            raise RuntimeError(f'Milly shutdown failed: {result.message}')
                        print('Milly shutdown completed.', flush=True)
                    else:
                        arm.disconnect()
    print('DXL torque OFF; port closed.', flush=True)


def main():
    p = parser(__doc__)
    p.add_argument('--product-id', required=True, help='robot ID engraved on the Milly arm')
    args = p.parse_args()
    try:
        dev, controller, profile = setup(args)
        import motomind_milly as mm
        mm.enable_logging()
        run_teleop(dev, controller, profile, lambda: mm.create_arm(args.product_id),
                   rate_hz=args.rate_hz, duration=args.duration)
        return 0
    except (KeyboardInterrupt, EOFError):
        print('Stopped by operator.')
        return 0
    except Exception as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
