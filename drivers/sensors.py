import machine
import dht

class SensorManager:
    def __init__(self, dht_pin=15, ldr_pin=34):
        # DHT22
        self.dht_sensor = dht.DHT22(machine.Pin(dht_pin))
        
        # LDR (ADC)
        self.ldr_adc = machine.ADC(machine.Pin(ldr_pin))
        self.ldr_adc.atten(machine.ADC.ATTN_11DB)
        self.ldr_adc.width(machine.ADC.WIDTH_12BIT)

    def get_temp_humidity(self):
        """Returns tuple (temperature, humidity) or (None, None) on error"""
        try:
            self.dht_sensor.measure()
            return self.dht_sensor.temperature(), self.dht_sensor.humidity()
        except Exception as e:
            print(f"[Sensor] DHT Error: {e}")
            return None, None

    def get_light_level(self):
        """Returns ADC value (0-4095)"""
        try:
            return self.ldr_adc.read()
        except Exception as e:
            print(f"[Sensor] LDR Error: {e}")
            return -1
