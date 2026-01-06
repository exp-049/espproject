class FuzzyPID:
    """
    Fuzzy-PID 控制器类 (Fuzzy-PID Controller)
    利用误差 (E) 和误差变化率 (EC) 进行模糊推理，自适应调整 PID 参数。
    包含固定的积分项 (I) 以消除稳态误差。
    """
    def __init__(self, target=0, kp_base=40.0, ki=0.5, kd_base=10.0):
        self.target = target
        self.kp_base = kp_base
        self.ki = ki
        self.kd_base = kd_base
        
        self.prev_error = 0
        self.integral = 0
        self.integral_limit = 500 # 积分限幅 (防止积分饱和 Windup)
        
        # 模糊集合定义 (Fuzzy Sets): 
        # NB (Negative Big, 负大) ... PB (Positive Big, 正大)
        # 索引映射: 0=NB, 1=NM, 2=NS, 3=ZO, 4=PS, 5=PM, 6=PB
        self.NB, self.NM, self.NS, self.ZO, self.PS, self.PM, self.PB = 0,1,2,3,4,5,6
        
        # 模糊规则表 (Fuzzy Rules for Kp Scaling)
        # 这是一个二维系数表，输出值为 Kp_base 的乘数。
        # 按照经验规则设计:
        # - 误差大时 (NB/PB): 大 P，加快响应
        # - 误差小时 (ZO): 小 P，减少超调，求稳
        
        # 行: 误差 E (NB->PB), 列: 误差变化率 EC (NB->PB)
        # self.kp_rules[E_index][EC_index]
        self.kp_rules = [
            # NB, NM, NS, ZO, PS, PM, PB (EC)
            [2.0, 2.0, 2.0, 2.0, 1.5, 1.2, 1.0], # NB (E) - 误差很大负
            [2.0, 2.0, 1.8, 1.8, 1.5, 1.0, 0.8], # NM
            [1.5, 1.5, 1.2, 1.0, 0.8, 0.5, 0.5], # NS
            [1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2], # ZO (E接近0) - 稳定区
            [0.5, 0.5, 0.8, 1.0, 1.2, 1.5, 1.5], # PS
            [0.8, 1.0, 1.5, 1.8, 1.8, 2.0, 2.0], # PM
            [1.0, 1.2, 1.5, 2.0, 2.0, 2.0, 2.0], # PB - 误差很大正
        ]
        
    def _fuzzify(self, val):
        """模糊化: 将输入数值映射到模糊集合索引 (0-6)。假设输入范围大致归一化在 -3 到 3 之间。"""
        if val < -3: return self.NB
        elif val < -2: return self.NM
        elif val < -1: return self.NS
        elif val < 1: return self.ZO
        elif val < 2: return self.PS
        elif val < 3: return self.PM
        else: return self.PB

    def compute(self, current_val):
        error = self.target - current_val           # 计算误差 E
        error_rate = error - self.prev_error        # 计算误差变化率 EC
        self.prev_error = error
        
        # 1. 积分项计算 (Integral)
        self.integral += error
        # 积分限幅
        if self.integral > self.integral_limit: self.integral = self.integral_limit
        if self.integral < -self.integral_limit: self.integral = -self.integral_limit
        
        # 2. 模糊推理调整 Kp (Fuzzy Logic)
        # 归一化输入 (比例因子需根据实际系统响应调整)
        # 假设温度误差 +/- 10度 算作“大”
        e_norm = error * 0.3      # 缩放至约 -3..3 范围
        ec_norm = error_rate * 2.0 # 变化率缩放
        
        e_idx = self._fuzzify(e_norm)
        ec_idx = self._fuzzify(ec_norm)
        
        # 解模糊 (查表法 Defuzzification)
        kp_scaler = self.kp_rules[e_idx][ec_idx]
        
        # 自适应参数计算
        kp = self.kp_base * kp_scaler
        kd = self.kd_base # Kd 暂时保持固定，简化设计
        
        # 3. 计算 PID 输出
        p_out = kp * error
        i_out = self.ki * self.integral
        d_out = kd * error_rate
        
        output = p_out + i_out + d_out
        
        # 输出限幅 (PWM 占空比映射前的修正)
        # 假设范围 -1023 到 1023 (后续会被映射到 0-65535)
        # 正值 = 加热, 负值 = 制冷(风扇)
        if output > 1023: output = 1023
        if output < -1023: output = -1023
        
        return output, (p_out, i_out, d_out)
