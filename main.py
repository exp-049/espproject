import time
import machine
from drivers.display import OLEDManager
from drivers.sensors import SensorManager
from drivers.actuators import ActuatorManager
from ir_decoder import NECRemote
from fuzzy_pid import FuzzyPID

# --- Constants ---
STATE_OFF = 0
STATE_RUN = 1
STATE_SET_TEMP = 2
STATE_SET_HUM = 3

class DisplayUI:
    def __init__(self):
        self.oled = OLEDManager()
        self.oled.init_display()
        self.oled.clear()

    def draw_status(self, temp, hum, target_temp, target_hum, mode, fan_status, heat_status):
        self.oled.clear()
        
        # Header: Mode
        mode_str = "OFF"
        if mode == STATE_RUN: mode_str = "RUN"
        elif mode == STATE_SET_TEMP: mode_str = "SET TEMP"
        elif mode == STATE_SET_HUM: mode_str = "SET HUM"
        
        self.oled.show_text(f"Mode: {mode_str}", 0, 0, clear_first=False)
        
        # Sensor Data
        self.oled.show_text(f"T: {temp:.1f}C / {target_temp}C", 0, 16, clear_first=False)
        self.oled.show_text(f"H: {hum:.1f}% / {target_hum}%", 0, 26, clear_first=False)
        
        # Actuator Status
        status_str = ""
        if heat_status > 0: status_str += "HEAT "
        if fan_status > 0: status_str += "FAN"
        self.oled.show_text(status_str, 0, 40, clear_first=False)
        
        self.oled.oled.show()

class SystemController:
    def __init__(self):
        # 1. Hardware Init
        self.ui = DisplayUI()
        self.sensors = SensorManager()
        self.actuators = ActuatorManager()
        self.actuators.init_actuators()
        
        # 2. Input Init (IR)
        # Using Interrupt based decoder
        self.ir = NECRemote(pin_num=35, callback=self.on_ir_command)
        
        # 3. Algorithm Init
        self.target_temp = 25.0
        self.target_hum = 60.0
        self.pid = FuzzyPID(target=self.target_temp)
        
        # 4. State
        self.state = STATE_OFF
        self.last_run_pid = 0
        self.last_ui_update = 0
        self.last_sensor_read = 0
        
        # Input Queue
        self.pending_key = None
        
        # Current Readings
        self.current_temp = 0.0
        self.current_hum = 0.0
        self.current_ldr = 0
        
        print("System Initialized. Waiting for Power On (IR: POWER)...")
        self.ui.oled.show_text("STANDBY", 30, 30)

    def on_ir_command(self, key):
        """Callback for IR commands - Runs in ISR! Keep it minimal."""
        # Just store the key to be processed in main loop
        self.pending_key = key

    def process_input(self):
        """Process pending IR keys in main loop context"""
        if not self.pending_key:
            return
            
        key = self.pending_key
        self.pending_key = None # Clear
        
        print(f"Processing IR Key: {key}")
        
        if key == 'POWER':
            if self.state == STATE_OFF:
                self.state = STATE_RUN
                print("System ON")
            else:
                self.state = STATE_OFF
                self.actuators.cleanup()
                self.actuators.init_actuators() # Re-init to safe state (0)
                print("System OFF")
                self.ui.oled.show_text("STANDBY", 30, 30)
        
        elif key == 'MUTE':
            # Feature: Silence Buzzer / Ack
            print("MUTE Action: Silencing Buzzer")
            self.actuators.buzzer.duty_u16(0)
            self.ui.oled.show_text("MUTE", 50, 50, clear_first=False)
            
        # Handle other keys only if ON
        if self.state != STATE_OFF:
            if key == 'MENU':
                # Cycle modes: RUN -> SET_TEMP -> SET_HUM -> RUN
                if self.state == STATE_RUN: self.state = STATE_SET_TEMP
                elif self.state == STATE_SET_TEMP: self.state = STATE_SET_HUM
                elif self.state == STATE_SET_HUM: self.state = STATE_RUN
                print(f"Mode Switched: {self.state}")
            
            elif key == '+':
                if self.state == STATE_SET_TEMP: 
                    self.target_temp += 1.0
                    self.pid.target = self.target_temp
                elif self.state == STATE_SET_HUM: 
                    self.target_hum += 5.0
            
            elif key == '-':
                if self.state == STATE_SET_TEMP: 
                    self.target_temp -= 1.0
                    self.pid.target = self.target_temp
                elif self.state == STATE_SET_HUM: 
                    self.target_hum -= 5.0

    def run_scheduler(self):
        """Main non-blocking loop"""
        while True:
            now = time.ticks_ms()
            
            # 0. Process Input (Highest Priority)
            self.process_input()
            
            if self.state != STATE_OFF:
                # 1. Read Sensors (2000ms)
                if time.ticks_diff(now, self.last_sensor_read) > 2000:
                    t, h = self.sensors.get_temp_humidity()
                    if t is not None: 
                        self.current_temp = t
                        self.current_hum = h
                    
                    # LDR Logic (Auto Dimmer)
                    self.current_ldr = self.sensors.get_light_level() # 0-4095
                    # Map LDR to LED brightness
                    # User feedback: Previous logic was reversed.
                    # Adjusted to: Higher LDR value -> Higher PWM (or vice versa as requested)
                    # Let's simply remove the '65535 -' inversion based on user request.
                    white_pwm = int((self.current_ldr / 4095) * 65535)
                    if white_pwm > 65535: white_pwm = 65535
                    self.actuators.pwms['light'].duty_u16(white_pwm)
                    
                    self.last_sensor_read = now

                # 2. Run PID Control (100ms)
                if time.ticks_diff(now, self.last_run_pid) > 100:
                    # Temperature Control (Fuzzy PID)
                    pid_out, _ = self.pid.compute(self.current_temp)
                    
                    # Actuator Mapping
                    # pid_out > 0: Heat (Red LED), Fan Off
                    # pid_out < 0: Cool (Green LED/Fan), Heat Off
                    heater_duty = 0
                    fan_duty = 0
                    
                    if pid_out > 0:
                        heater_duty = int(abs(pid_out) * 64) # Scale 1023 to 65535 approx (x64)
                        if heater_duty > 65535: heater_duty = 65535
                        fan_duty = 0
                    else:
                        heater_duty = 0
                        fan_duty = int(abs(pid_out) * 64)
                        if fan_duty > 65535: fan_duty = 65535
                        
                    self.actuators.pwms['heater'].duty_u16(heater_duty)
                    self.actuators.pwms['fan'].duty_u16(fan_duty)
                    
                    # Humidity Control (Bang-Bang Hysteresis)
                    # Target 60%. Deadband 5% -> On if < 57.5, Off if > 62.5
                    # Humidifier = Buzzer (PWM)
                    # Logic: If Hum < (Target - 2.5), Turn On. If Hum > (Target + 2.5), Turn Off.
                    deadband = 2.5
                    if self.current_hum < (self.target_hum - deadband):
                        # Turn On Humidifier (Buzzer 2kHz)
                         # Check if already on to avoid resetting phase/sound annoying
                        if self.actuators.buzzer.duty_u16() == 0:
                            self.actuators.buzzer.freq(2000)
                            self.actuators.buzzer.duty_u16(32768)
                    elif self.current_hum > (self.target_hum + deadband):
                         self.actuators.buzzer.duty_u16(0)
                    
                    self.last_run_pid = now

                # 3. Update UI (200ms)
                if time.ticks_diff(now, self.last_ui_update) > 200:
                    heat_state = self.actuators.pwms['heater'].duty_u16()
                    fan_state = self.actuators.pwms['fan'].duty_u16()
                    
                    self.ui.draw_status(
                        self.current_temp, 
                        self.current_hum, 
                        self.target_temp, 
                        self.target_hum,
                        self.state,
                        fan_state,
                        heat_state
                    )
                    self.last_ui_update = now

            time.sleep(0.01) # Yield to system

if __name__ == "__main__":
    controller = SystemController()
    controller.run_scheduler()
