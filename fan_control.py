#!/usr/bin/env python3
"""
Noctua NF-A4x105v PWM fan controller for Raspberry Pi
PWM  : GPIO12 (BCM) - hardware PWM via gpiozero (lgpio backend)
Tach : GPIO16 (BCM) - 2 pulses per revolution
"""

import time

from gpiozero import DigitalInputDevice, PWMOutputDevice

PWM_PIN = 12
TACH_PIN = 16
PWM_FREQ = 10000  # 10kHz - the max frequency the lgpio backend will accept
                  # (Noctua's own spec calls for 25kHz, but lgpio caps out at 10kHz)

TEMP_MIN = 45.0   # fan starts spinning at this CPU temp (C)
TEMP_MAX = 80.0   # fan hits 100% at this CPU temp (C)
DUTY_MIN = 30     # minimum duty % that reliably spins the fan once started
DUTY_MAX = 100
DUTY_OFF = 0

POLL_INTERVAL = 2       # seconds between control loop iterations
TACH_SAMPLE_TIME = 1.0  # seconds spent sampling tach pulses each loop


def read_cpu_temp():
    with open("/sys/class/thermal/thermal_zone0/temp") as f:
        return int(f.read().strip()) / 1000.0


def temp_to_duty(temp):
    if temp <= TEMP_MIN:
        return DUTY_OFF
    if temp >= TEMP_MAX:
        return DUTY_MAX
    ratio = (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    return DUTY_MIN + ratio * (DUTY_MAX - DUTY_MIN)


class TachCounter:
    """Counts tach pulses on a pulled-up input; Noctua fans emit 2 pulses/rev."""

    def __init__(self, gpio):
        self.count = 0
        self.device = DigitalInputDevice(gpio, pull_up=True)
        self.device.when_activated = self._pulse  # fires on the falling edge

    def _pulse(self):
        self.count += 1

    def read_rpm(self, sample_time):
        self.count = 0
        time.sleep(sample_time)
        pulses = self.count
        return (pulses / 2.0) / sample_time * 60.0

    def close(self):
        self.device.close()


def main():
    fan_pwm = PWMOutputDevice(PWM_PIN, frequency=PWM_FREQ, initial_value=0)
    tach = TachCounter(TACH_PIN)

    try:
        while True:
            temp = read_cpu_temp()
            duty = temp_to_duty(temp)
            fan_pwm.value = duty / 100.0

            rpm = tach.read_rpm(TACH_SAMPLE_TIME)
            print(f"CPU: {temp:.1f}C  Duty: {duty:.0f}%  RPM: {rpm:.0f}", flush=True)

            remaining = POLL_INTERVAL - TACH_SAMPLE_TIME
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    finally:
        fan_pwm.value = 0
        fan_pwm.close()
        tach.close()


if __name__ == "__main__":
    main()
