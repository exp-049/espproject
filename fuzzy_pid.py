class FuzzyPID:
    """
    Fuzzy-PID Controller.
    Uses error (E) and change of error (EC) to output control signal (PWM duty).
    Includes fixed Integral term for steady-state error elimination.
    """
    def __init__(self, target=0, kp_base=40.0, ki=0.5, kd_base=10.0):
        self.target = target
        self.kp_base = kp_base
        self.ki = ki
        self.kd_base = kd_base
        
        self.prev_error = 0
        self.integral = 0
        self.integral_limit = 500 # Prevent windup
        
        # Fuzzy Sets: NB (Negative Big) ... PB (Positive Big)
        # Mapping index: 0=NB, 1=NM, 2=NS, 3=ZO, 4=PS, 5=PM, 6=PB
        self.NB, self.NM, self.NS, self.ZO, self.PS, self.PM, self.PB = 0,1,2,3,4,5,6
        
        # Fuzzy Rules Table for Kp scaling (simplified)
        # Typically: Large error -> Large Kp. Small error -> Medium Kp? 
        # Actually for stability: Large error -> Large P (get there fast). Small error -> Small P (reduce overshoot).
        # We'll use a Coefficient Table: Output is a multiplier for Kp_base
        
        # Rows: Error (NB to PB), Cols: EC (NB to PB)
        # This is a classic Tuning Rule base.
        # Format: self.kp_rules[E_index][EC_index]
        self.kp_rules = [
            # NB, NM, NS, ZO, PS, PM, PB (EC)
            [2.0, 2.0, 2.0, 2.0, 1.5, 1.2, 1.0], # NB (E)
            [2.0, 2.0, 1.8, 1.8, 1.5, 1.0, 0.8], # NM
            [1.5, 1.5, 1.2, 1.0, 0.8, 0.5, 0.5], # NS
            [1.2, 1.0, 1.0, 1.0, 1.0, 1.0, 1.2], # ZO (Stable)
            [0.5, 0.5, 0.8, 1.0, 1.2, 1.5, 1.5], # PS
            [0.8, 1.0, 1.5, 1.8, 1.8, 2.0, 2.0], # PM
            [1.0, 1.2, 1.5, 2.0, 2.0, 2.0, 2.0], # PB
        ]
        
    def _fuzzify(self, val):
        """Maps input value to fuzzy set index (0-6). range -100 to 100 roughly."""
        if val < -3: return self.NB
        elif val < -2: return self.NM
        elif val < -1: return self.NS
        elif val < 1: return self.ZO
        elif val < 2: return self.PS
        elif val < 3: return self.PM
        else: return self.PB

    def compute(self, current_val):
        error = self.target - current_val
        error_rate = error - self.prev_error
        self.prev_error = error
        
        # 1. Integral Term (Independent I)
        self.integral += error
        if self.integral > self.integral_limit: self.integral = self.integral_limit
        if self.integral < -self.integral_limit: self.integral = -self.integral_limit
        
        # 2. Fuzzy Logic for Kp
        # Normalize inputs for fuzzification (Scale factors need tuning)
        # Assume Temp error range +/- 10 degrees is "Large"
        e_norm = error * 0.3 # Scale to approx -3..3 range
        ec_norm = error_rate * 2.0
        
        e_idx = self._fuzzify(e_norm)
        ec_idx = self._fuzzify(ec_norm)
        
        # Defuzzify (Lookup table)
        kp_scaler = self.kp_rules[e_idx][ec_idx]
        
        # Adaptive Gains
        kp = self.kp_base * kp_scaler
        kd = self.kd_base # Keep Kd simple/fixed for this minimal implementation
        
        # 3. PID Output Calculation
        p_out = kp * error
        i_out = self.ki * self.integral
        d_out = kd * error_rate
        
        output = p_out + i_out + d_out
        
        # Clamp output for PWM (-1023 to 1023)
        # Positive = Heating, Negative = Cooling (Fan)
        if output > 1023: output = 1023
        if output < -1023: output = -1023
        
        return output, (p_out, i_out, d_out)
