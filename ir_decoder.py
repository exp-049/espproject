import time
from machine import Pin

class NECRemote:
    """
    NEC 红外遥控解码器 (NEC IR Decoder)
    使用 GPIO 中断方式捕获脉冲信号，非阻塞解码。
    """
    def __init__(self, pin_num, callback=None):
        self.pin = Pin(pin_num, Pin.IN)
        self.callback = callback
        self.t_last = 0
        self.pulses = []
        # 配置双边沿触发中断，以便捕获高低电平持续时间
        self.pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._irq_handler)
        
        # 标准 NEC 键值映射表 (参考常见 MP3 开发板遥控器)
        # 建议实际使用前打印键值校验
        self.key_map = {
            0x45: 'POWER',
            0x47: 'MENU', 
            0x44: 'MUTE', # 测试键映射为静音
            0x40: '+',
            0x43: 'BACK',
            0x07: 'PREV',
            0x15: 'PLAY',
            0x09: 'NEXT',
            0x16: '0',
            0x19: '-',
            0x0d: 'C',
            0x0c: '1',
            0x18: '2',
            0x5e: '3',
            0x08: '4',
            0x1c: '5',
            0x5a: '6',
            0x42: '7',
            0x52: '8',
            0x4a: '9'
        }
        
        self.last_key = None
        self.last_key_time = 0

    def _irq_handler(self, pin):
        """中断服务函数: 记录脉冲宽度"""
        t = time.ticks_us()
        dt = time.ticks_diff(t, self.t_last)
        self.t_last = t
        
        # NEC 协议逻辑:
        # 引导码 (Header): 9ms 低电平 + 4.5ms 高电平
        # 我们根据时间差判断信号段
        
        if dt > 10000: # 超过 10ms 的间隔，视为新的一帧指令开始
            self.pulses = []
        
        self.pulses.append(dt)
        
        # 完整的 NEC 编码包含 32位数据 + 引导码 + 结束位 (~67次电平翻转)
        if len(self.pulses) >= 67:
            # print(f"DEBUG: 捕获脉冲数: {len(self.pulses)}") 
            self._decode()
            self.pulses = []

    def _decode(self):
        try:
            # pulses[0] 是帧间隔 (长静默)
            # pulses[1] 应为 ~9ms 的引导码起始(Mark)
            # pulses[2] 应为 ~4.5ms 的引导码间隔(Space) 或 ~2.25ms (重复码)
            
            if len(self.pulses) < 3: return
            
            # 校验引导码 (Mark)
            # 范围放宽到 8-10ms (标准 9ms)
            if not (8000 < self.pulses[1] < 10000):
                return
            
            # 校验 Space
            # 标准 NEC: ~4500us
            # 重复码 (Repeat): ~2250us
            if 4000 < self.pulses[2] < 5000:
                pass # 正常引导码
            elif 2000 < self.pulses[2] < 3000:
                # 收到重复码 (长按效果)，此处暂忽略以防误触
                return 
            else:
                return # 无效头
            
            # 解析数据位
            # 数据位从索引 3 开始 (脉冲) -> 4 (间隔) -> 5 ...
            # 逻辑 '0': 560us 脉冲 + 560us 间隔
            # 逻辑 '1': 560us 脉冲 + 1690us 间隔
            # 我们通过判断"间隔"的时长来区分 0 和 1
            
            # 跳过头部，获取后续脉冲
            data_pulses = self.pulses[3:] 
            
            # 至少需要 32位数据 (即 64个跳变)
            if len(data_pulses) < 63: 
                return
            
            bit_count = 0
            val = 0
            
            # 步长为 2，只看间隔时长 (Indices 1, 3, 5...)
            for i in range(1, len(data_pulses), 2):
                space_len = data_pulses[i]
                
                # 阈值判断：大于 1000us 视为逻辑 '1' (标准 1690us)
                if space_len > 1000: 
                    val = (val << 1) | 1
                else:
                    val = (val << 1)
                
                bit_count += 1
                if bit_count == 32:
                    break
            
            if bit_count < 32:
                # 解码位数不足
                return

            # 数据结构: [地址 8bit] [~地址 8bit] [命令 8bit] [~命令 8bit]
            # 目前只取 Cmd 部分
            # 注意: NEC 发送通常是 LSB 优先，但此处直接移位处理
            # 只要能匹配到 key_map 即可 (反向亦可，只要映射表对应)
            
            cmd = (val >> 8) & 0xFF
            cmd_inv = val & 0xFF
            
            # 校验: 命令码应与反码互补 (cmd ^ cmd_inv == 0xFF)
            # 为提高兼容性，此处不做严格校验，直接查表
            
            if True: 
                 # print(f"[红外调试] 接收到 Hex: {cmd:02x}") # 调试用
                 if cmd in self.key_map:
                    key = self.key_map[cmd]
                    
                    # 软件消抖
                    # 200ms 内不重复响应同一按键
                    now = time.ticks_ms()
                    if key == self.last_key and time.ticks_diff(now, self.last_key_time) < 200:
                        return # 忽略
                    
                    self.last_key = key
                    self.last_key_time = now
                    # print(f"[红外] 解析键值: {key} (Hex: {cmd:02x})")
                    if self.callback:
                        self.callback(key)
        except Exception as e:
            print(f"红外解码错误: {e}")

    def get_last_key(self):
        """获取最近按下的键值 (200ms有效期)"""
        if time.ticks_diff(time.ticks_ms(), self.last_key_time) < 200:
            return self.last_key
        return None
