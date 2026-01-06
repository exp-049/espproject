import machine
import time

class ActuatorManager:
    def __init__(self, heater_pin=25, fan_pin=26, light_pin=14, buzzer_pin=27):
        self.pins = {
            'heater': heater_pin,
            'fan': fan_pin,
            'light': light_pin
        }
        self.buzzer_pin = buzzer_pin
        self.pwms = {}
        self.buzzer = None

    def init_actuators(self):
        # LEDs
        for name, pin_num in self.pins.items():
            pwm = machine.PWM(machine.Pin(pin_num))
            pwm.freq(1000)
            pwm.duty_u16(0)
            self.pwms[name] = pwm
        
        # Buzzer
        self.buzzer = machine.PWM(machine.Pin(self.buzzer_pin))
        self.buzzer.freq(2000)
        self.buzzer.duty_u16(0)

    def set_led_breathing(self):
        print("Running LED Breathing Effect...")
        pwms = list(self.pwms.values())
        
        # Rise
        for i in range(0, 65535, 2000):
            for pwm in pwms:
                pwm.duty_u16(i)
            time.sleep(0.02)
        
        # Fall
        for i in range(65535, 0, -2000):
            for pwm in pwms:
                pwm.duty_u16(i)
            time.sleep(0.02)
        
        # Off
        for pwm in pwms:
            pwm.duty_u16(0)

    def beep_buzzer(self, freq=2000, duration=0.5):
        if not self.buzzer:
            return
        self.buzzer.freq(freq)
        self.buzzer.duty_u16(32768) # 50%
        time.sleep(duration)
        self.buzzer.duty_u16(0)

    def cleanup(self):
        for pwm in self.pwms.values():
            pwm.duty_u16(0)
            pwm.deinit()
        if self.buzzer:
            self.buzzer.duty_u16(0)
            self.buzzer.deinit()
