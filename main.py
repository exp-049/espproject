import time
import machine
from drivers.display import OLEDManager
from drivers.sensors import SensorManager
from drivers.actuators import ActuatorManager
from ir_decoder import NECRemote
from fuzzy_pid import FuzzyPID

# --- 全局常量定义 ---
STATE_OFF = 0       # 关机 (待机)
STATE_RUN = 1       # 运行 (自动控制)
STATE_SET_TEMP = 2  # 设置目标温度
STATE_SET_HUM = 3   # 设置目标湿度

class DisplayUI:
    """
    界面显示类
    负责 OLED 屏幕的状态显示与逻辑渲染。
    """
    def __init__(self):
        self.oled = OLEDManager()
        self.oled.init_display()
        self.oled.clear()

    def draw_status(self, temp, hum, target_temp, target_hum, mode, fan_status, heat_status):
        """
        绘制主状态界面 (局部刷新)
        :param temp: 当前温度
        :param hum: 当前湿度
        :param target_temp: 目标温度
        :param target_hum: 目标湿度
        :param mode: 当前工作模式
        :param fan_status: 风扇 PWM 值
        :param heat_status: 加热器 PWM 值
        """
        self.oled.clear()
        
        # 1. 显示模式标题
        mode_str = "OFF"
        if mode == STATE_RUN: mode_str = "RUN"
        elif mode == STATE_SET_TEMP: mode_str = "SET TEMP"
        elif mode == STATE_SET_HUM: mode_str = "SET HUM"
        
        self.oled.show_text(f"Mode: {mode_str}", 0, 0, clear_first=False)
        
        # 2. 显示传感器数据与目标值
        self.oled.show_text(f"T: {temp:.1f}C / {target_temp}C", 0, 16, clear_first=False)
        self.oled.show_text(f"H: {hum:.1f}% / {target_hum}%", 0, 26, clear_first=False)
        
        # 3. 显示执行器状态 (底部栏)
        status_str = ""
        if heat_status > 0: status_str += "HEAT " # 加热中
        if fan_status > 0: status_str += "FAN"   # 风扇转
        self.oled.show_text(status_str, 0, 40, clear_first=False)
        
        self.oled.oled.show()

class SystemController:
    """
    系统主控制器类 (Main Controller)
    集成传感器、执行器、交互逻辑与控制算法，通过时间片轮询实现多任务调度。
    """
    def __init__(self):
        # 1. 硬件驱动初始化
        self.ui = DisplayUI()
        self.sensors = SensorManager()
        self.actuators = ActuatorManager()
        self.actuators.init_actuators()
        
        # 2. 输入设备初始化 (红外)
        # 使用中断回调方式接收指令
        self.ir = NECRemote(pin_num=35, callback=self.on_ir_command)
        
        # 3. 算法初始化
        self.target_temp = 25.0
        self.target_hum = 60.0
        self.pid = FuzzyPID(target=self.target_temp)
        
        # 4. 系统变量初始化
        self.state = STATE_OFF
        self.last_run_pid = 0
        self.last_ui_update = 0
        self.last_sensor_read = 0
        
        # 输入指令队列 (循环缓冲区)
        self.pending_key = None
        
        # 当前传感器读数缓存
        self.current_temp = 0.0
        self.current_hum = 0.0
        self.current_ldr = 0
        
        print("系统初始化完成。等待开机指令 (红外: POWER)...")
        self.ui.oled.show_text("STANDBY", 30, 30)

    def on_ir_command(self, key):
        """红外中断回调函数 (ISR 上下文) - 仅做数据缓存，不处理耗时逻辑"""
        self.pending_key = key

    def process_input(self):
        """在主循环中处理输入指令"""
        if not self.pending_key:
            return
            
        key = self.pending_key
        self.pending_key = None # 清除缓存
        
        print(f"收到指令: {key}")
        
        if key == 'POWER':
            if self.state == STATE_OFF:
                self.state = STATE_RUN
                print("系统已启动 (ON)")
            else:
                self.state = STATE_OFF
                self.actuators.cleanup() # 安全复位执行器
                self.actuators.init_actuators() # 重新初始化为 0 状态
                print("系统已关闭 (OFF)")
                self.ui.oled.show_text("STANDBY", 30, 30)
        
        elif key == 'MUTE':
            # 功能: 静音蜂鸣器 / 确认
            print("静音操作: 关闭蜂鸣器")
            self.actuators.buzzer.duty_u16(0)
            self.ui.oled.show_text("MUTE", 50, 50, clear_first=False)
            
        # 仅在非关机状态下响应其他按键
        if self.state != STATE_OFF:
            if key == 'MENU':
                # 模式切换: RUN -> SET_TEMP -> SET_HUM -> RUN
                if self.state == STATE_RUN: self.state = STATE_SET_TEMP
                elif self.state == STATE_SET_TEMP: self.state = STATE_SET_HUM
                elif self.state == STATE_SET_HUM: self.state = STATE_RUN
                print(f"模式已切换: {self.state}")
            
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
        """主循环调度器 (非阻塞)"""
        while True:
            now = time.ticks_ms()
            
            # 0. 处理输入 (最高优先级)
            self.process_input()
            
            if self.state != STATE_OFF:
                # 1. 读取传感器 (每2000ms)
                if time.ticks_diff(now, self.last_sensor_read) > 2000:
                    t, h = self.sensors.get_temp_humidity()
                    if t is not None: 
                        self.current_temp = t
                        self.current_hum = h
                    
                    # 光控逻辑 (环境越暗，补光灯越亮 -> 这里根据用户需求：数值越大越亮)
                    self.current_ldr = self.sensors.get_light_level() # 0-4095
                    # 映射逻辑 (简单比例)
                    white_pwm = int((self.current_ldr / 4095) * 65535)
                    if white_pwm > 65535: white_pwm = 65535
                    self.actuators.pwms['light'].duty_u16(white_pwm)
                    
                    self.last_sensor_read = now

                # 2. 运行 PID 控制算法 (每100ms)
                if time.ticks_diff(now, self.last_run_pid) > 100:
                    # 温度控制 (Fuzzy PID)
                    pid_out, _ = self.pid.compute(self.current_temp)
                    
                    # 执行器映射
                    # pid_out > 0: 需要加热 (红灯)，关风扇
                    # pid_out < 0: 需要制冷 (绿灯/风扇)，关加热
                    heater_duty = 0
                    fan_duty = 0
                    
                    if pid_out > 0:
                        heater_duty = int(abs(pid_out) * 64) # 缩放 1023 到 65535 (x64)
                        if heater_duty > 65535: heater_duty = 65535
                        fan_duty = 0
                    else:
                        heater_duty = 0
                        fan_duty = int(abs(pid_out) * 64)
                        if fan_duty > 65535: fan_duty = 65535
                        
                    self.actuators.pwms['heater'].duty_u16(heater_duty)
                    self.actuators.pwms['fan'].duty_u16(fan_duty)
                    
                    # 湿度控制 (滞回比较 Bang-Bang Hysteresis)
                    # 目标 60%. 死区 2.5% -> 小于 57.5% 加湿, 大于 62.5% 停止
                    # 加湿器 = 蜂鸣器模拟
                    deadband = 2.5
                    if self.current_hum < (self.target_hum - deadband):
                        # 开启加湿器 (蜂鸣器 2kHz)
                         # 检查是否已开启，避免重复打断音频
                        if self.actuators.buzzer.duty_u16() == 0:
                            self.actuators.buzzer.freq(2000)
                            self.actuators.buzzer.duty_u16(32768)
                    elif self.current_hum > (self.target_hum + deadband):
                         self.actuators.buzzer.duty_u16(0)
                    
                    self.last_run_pid = now

                # 3. 刷新 UI 界面 (每200ms)
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

            time.sleep(0.01) # 让出 CPU 时间片，防止死锁

if __name__ == "__main__":
    controller = SystemController()
    controller.run_scheduler()
