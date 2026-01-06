import machine
import dht

class SensorManager:
    """
    传感器管理类 (Sensor Manager)
    负责初始化和读取 DHT22 温湿度传感器与 LDR 光敏电阻的数据。
    """
    def __init__(self, dht_pin=15, ldr_pin=34):
        # 初始化 DHT22 温湿度传感器
        # 注意: DHT22 对时序要求严格，建议使用 4.7k-10k 上拉电阻
        self.dht_sensor = dht.DHT22(machine.Pin(dht_pin))
        
        # 初始化 LDR 光敏电阻 (使用 ADC 读取模拟电压)
        self.ldr_adc = machine.ADC(machine.Pin(ldr_pin))
        # 设置 ADC 衰减为 11dB，这将量程扩展到 0-3.6V (ESP32 默认仅 1.1V)
        self.ldr_adc.atten(machine.ADC.ATTN_11DB)
        # 设置分辨率为 12位 (0-4095)
        self.ldr_adc.width(machine.ADC.WIDTH_12BIT)

    def get_temp_humidity(self):
        """
        读取温湿度数据
        :return: (温度, 湿度) 元组，如果读取失败返回 (None, None)
        """
        try:
            self.dht_sensor.measure() # 触发一次测量
            return self.dht_sensor.temperature(), self.dht_sensor.humidity()
        except Exception as e:
            print(f"[传感器] DHT 读取错误: {e}")
            return None, None

    def get_light_level(self):
        """
        获取环境光照强度
        :return: ADC 数值 (0-4095), 数值越大越亮(视电路连接而定)
        """
        try:
            return self.ldr_adc.read()
        except Exception as e:
            print(f"[传感器] LDR 读取错误: {e}")
            return -1
