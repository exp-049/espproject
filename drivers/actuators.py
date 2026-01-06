import machine
import time

class ActuatorManager:
    """
    执行器管理类 (Actuator Manager)
    负责控制 LED (加热/风扇/补光) 和 蜂鸣器 (报警/加湿模拟)。
    """
    def __init__(self, heater_pin=25, fan_pin=26, light_pin=14, buzzer_pin=27):
        # 定义执行器引脚映射
        self.pins = {
            'heater': heater_pin, # 红色 LED 模拟加热器
            'fan': fan_pin,       # 绿色 LED 模拟风扇
            'light': light_pin    # 白色 LED 模拟补光灯
        }
        self.buzzer_pin = buzzer_pin
        self.pwms = {} # 存储 PWM 对象
        self.buzzer = None

    def init_actuators(self):
        """初始化所有 PWM 通道"""
        # 初始化 LED PWM
        for name, pin_num in self.pins.items():
            pwm = machine.PWM(machine.Pin(pin_num))
            pwm.freq(1000) # 设置频率为 1kHz
            pwm.duty_u16(0) # 初始占空比为 0 (关闭)
            self.pwms[name] = pwm
        
        # 初始化蜂鸣器 PWM
        self.buzzer = machine.PWM(machine.Pin(self.buzzer_pin))
        self.buzzer.freq(2000) # 初始频率 2kHz
        self.buzzer.duty_u16(0) # 初始静音

    def set_led_breathing(self):
        """LED 呼吸灯与自检效果 (阻塞式)"""
        print("执行 LED 呼吸灯自检...")
        pwms = list(self.pwms.values())
        
        # 渐亮 (Rise)
        for i in range(0, 65535, 2000):
            for pwm in pwms:
                pwm.duty_u16(i)
            time.sleep(0.02)
        
        # 渐暗 (Fall)
        for i in range(65535, 0, -2000):
            for pwm in pwms:
                pwm.duty_u16(i)
            time.sleep(0.02)
        
        # 关闭所有 (Off)
        for pwm in pwms:
            pwm.duty_u16(0)

    def beep_buzzer(self, freq=2000, duration=0.5):
        """控制蜂鸣器鸣叫指定时长 (阻塞式)"""
        if not self.buzzer:
            return
        self.buzzer.freq(freq)
        self.buzzer.duty_u16(32768) # 50% 占空比发声最响
        time.sleep(duration)
        self.buzzer.duty_u16(0)     # 停止发声

    def cleanup(self):
        """资源释放与复位"""
        for pwm in self.pwms.values():
            pwm.duty_u16(0)
            pwm.deinit()
        if self.buzzer:
            self.buzzer.duty_u16(0)
            self.buzzer.deinit()
