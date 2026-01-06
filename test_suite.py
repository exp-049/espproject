import time
from drivers.display import OLEDManager
from drivers.sensors import SensorManager
from drivers.actuators import ActuatorManager
from drivers.ir import IRManager

class HardwareTestSuite:
    def __init__(self):
        self.display = OLEDManager()
        self.sensors = SensorManager()
        self.actuators = ActuatorManager()
        self.ir = IRManager()

    def run_all_tests(self):
        print("=== Initializes Modules ===")
        # Init specific hardware
        if not self.display.init_display():
            print("Display Init Failed")
        
        self.actuators.init_actuators()

        print("\n=== STARTING HARDWARE SUITE ===")
        
        # 1. Display Test
        print("\n[TEST 1] OLED Display")
        self.display.draw_box()
        self.display.show_text("Modular Test", 10, 10, clear_first=False)
        time.sleep(2)

        # 2. Sensor Test
        print("\n[TEST 2] Sensors")
        t, h = self.sensors.get_temp_humidity()
        print(f"DHT22: {t}C, {h}%")
        
        ldr = self.sensors.get_light_level()
        print(f"LDR: {ldr}")
        time.sleep(2)

        # 3. Actuator Test
        print("\n[TEST 3] Actuators")
        self.actuators.set_led_breathing()
        print("Beeping...")
        self.actuators.beep_buzzer()
        time.sleep(2)

        # 4. IR Test
        print("\n[TEST 4] IR Signal")
        ir_val = self.ir.read_state()
        print(f"IR Pin State: {ir_val}")

        print("\n=== SUITE COMPLETED ===")
        
        # Cleanup (Optional)
        self.actuators.cleanup()

if __name__ == "__main__":
    suite = HardwareTestSuite()
    suite.run_all_tests()
