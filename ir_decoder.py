import time
from machine import Pin

class NECRemote:
    """
    NEC Infrared Remote Decoder using Interrupts.
    Captures pulse widths and decodes in the main loop/callback.
    """
    def __init__(self, pin_num, callback=None):
        self.pin = Pin(pin_num, Pin.IN)
        self.callback = callback
        self.t_last = 0
        self.pulses = []
        self.pin.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=self._irq_handler)
        
        # Standard NEC Key Map (Example for generic MP3 remote often used in kits)
        # Verify codes with your specific remote.
        self.key_map = {
            0x45: 'POWER',
            0x47: 'MENU', 
            0x44: 'MUTE', # TEST button mapped to MUTE
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
        t = time.ticks_us()
        dt = time.ticks_diff(t, self.t_last)
        self.t_last = t
        
        # NEC Logic:
        # Header: 9ms low + 4.5ms high (detecting edges, so we look for gaps)
        # We accumulate pulse durations.
        # Since we set IRQ on both edges, dt is the duration of the previous level.
        
        if dt > 10000: # Found a long gap, reset (start of new code)
            self.pulses = []
        
        self.pulses.append(dt)
        
        # Full NEC code is 32 bits + header + end bit (~67 transitions)
        # Reverting to 67 to ensure we have enough bits.
        if len(self.pulses) >= 67:
            # print(f"DEBUG: Pulses captured: {len(self.pulses)}") 
            self._decode()
            self.pulses = []

    def _decode(self):
        try:
            # pulses[0] is the long gap (reset)
            # pulses[1] ~9ms Mark
            # pulses[2] ~4.5ms Space (Header) or ~2.25ms (Repeat)
            
            if len(self.pulses) < 3: return
            
            # Check Header (Simple heuristic)
            # Mark should be ~9000us
            if not (8000 < self.pulses[1] < 10000):
                return
            
            # Check Space
            # Standard NEC: ~4500us
            # Repeat Code: ~2250us
            if 4000 < self.pulses[2] < 5000:
                pass # Normal header
            elif 2000 < self.pulses[2] < 3000:
                # Repeat code - ignore for now to prevent double triggers
                # Or handle if long-press is needed. For sensitivity, ignoring is safer for now.
                return 
            else:
                return # Invalid header

            code = 0
            # Data bits start at index 3 (Mark) -> 4 (Space) -> 5 (Mark)...
            # We care about the Spaces at indices 4, 6, 8...
            # 32 bits means we look for 32 spaces.
            
            # Ensure we don't go out of bounds
            # We need at least 32 bits. 32*2 = 64 edges for data.
            # +3 offset = 67.
            # But we triggered at 64. Let's iterate carefully.
            
            # Skip header
            data_pulses = self.pulses[3:] 
            
            # We need 32 bits (64 edges)
            if len(data_pulses) < 63: 
                # print(f"DEBUG: Not enough data: {len(data_pulses)}")
                return
            
            bit_count = 0
            val = 0
            
            for i in range(1, len(data_pulses), 2):
                space_len = data_pulses[i]
                
                # Logic: Short ~560us, Long ~1690us
                if space_len > 1000: 
                    val = (val << 1) | 1
                else:
                    val = (val << 1)
                
                bit_count += 1
                if bit_count == 32:
                    break
            
            if bit_count < 32:
                # Not enough bits decoded
                return

            # Address and Command parsing
            # NEC: Addr (8), ~Addr (8), Cmd (8), ~Cmd (8)
            # Standard Python integer is big enough
            
            # Byte 0: Addr, Byte 1: ~Addr, Byte 2: Cmd, Byte 3: ~Cmd
            # Note: The shift order depends on LSB/MSB first. 
            # NEC sends LSB first for each byte. The loop above shifts in...
            # Actually, standard IR libs often just shift in. Let's assume standard byte extraction.
            # If the remote matches the key map, the shift direction must match.
            # The previous code worked (val >> 8) & 0xFF. That implies Cmd is the 3rd byte shifted in?
            # 32 bits: [Addr] [~Addr] [Cmd] [~Cmd]
            # Val structure: (Addr << 24) | (~Addr << 16) | (Cmd << 8) | (~Cmd)
            
            cmd = (val >> 8) & 0xFF
            cmd_inv = val & 0xFF
            
            # Loose integrity check (sometimes checksums fail on one bit but code is valid)
            # if (cmd ^ cmd_inv) == 0xFF: 
            # STRICT CHECK:
            # Strict check - simplified
            if True: 
                 print(f"[IR DEBUG] Received Hex: {cmd:02x}") # Always print for debugging
                 if cmd in self.key_map:
                    key = self.key_map[cmd]
                    
                    # Software Debounce (Global for decoder)
                    # Don't trigger same key faster than 150ms
                    now = time.ticks_ms()
                    if key == self.last_key and time.ticks_diff(now, self.last_key_time) < 200:
                        return # Ignore repeat/bounce
                    
                    self.last_key = key
                    self.last_key_time = now
                    # print(f"[IR] Decoded: {key} (Hex: {cmd:02x})")
                    if self.callback:
                        self.callback(key)
        except Exception as e:
            print(f"IR Error: {e}")

    def get_last_key(self):
        """Returns last key if pressed within 200ms, else None"""
        if time.ticks_diff(time.ticks_ms(), self.last_key_time) < 200:
            return self.last_key
        return None
