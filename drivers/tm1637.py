"""
MicroPython TM1637 quad 7-segment LED display driver
"""
from machine import Pin
from time import sleep_us

TM1637_CMD1 = 64  # 0x40 data set
TM1637_CMD2 = 192 # 0xC0 address set
TM1637_CMD3 = 128 # 0x80 display control
TM1637_DSP_ON = 8 # 0x08 display on
TM1637_DELAY = 10 # 10us delay between clk/dio pulses

_SEGMENTS = bytearray(
    [
        0x3F, # 0
        0x06, # 1
        0x5B, # 2
        0x4F, # 3
        0x66, # 4
        0x6D, # 5
        0x7D, # 6
        0x07, # 7
        0x7F, # 8
        0x6F, # 9
        0x77, # A
        0x7C, # b
        0x39, # C
        0x5E, # d
        0x79, # E
        0x71, # F
    ]
)

class TM1637:
    """
    TM1637 4-Digit 7-Segment Display Driver
    """
    def __init__(self, clk, dio, brightness=7):
        self.clk = clk
        self.dio = dio

        if not isinstance(self.clk, Pin):
            self.clk = Pin(self.clk, Pin.OUT)
        if not isinstance(self.dio, Pin):
            self.dio = Pin(self.dio, Pin.OUT)

        self.clk.init(Pin.OUT, value=0)
        self.dio.init(Pin.OUT, value=0)
        self.brightness(brightness)

    def _start(self):
        self.dio.value(0)
        sleep_us(TM1637_DELAY)
        self.clk.value(0)
        sleep_us(TM1637_DELAY)

    def _stop(self):
        self.dio.value(0)
        sleep_us(TM1637_DELAY)
        self.clk.value(1)
        sleep_us(TM1637_DELAY)
        self.dio.value(1)

    def _write_byte(self, b):
        for i in range(8):
            self.dio.value((b >> i) & 1)
            sleep_us(TM1637_DELAY)
            self.clk.value(1)
            sleep_us(TM1637_DELAY)
            self.clk.value(0)
            sleep_us(TM1637_DELAY)
        self.clk.value(0)
        sleep_us(TM1637_DELAY)
        self.clk.value(1)
        sleep_us(TM1637_DELAY)
        self.clk.value(0)
        sleep_us(TM1637_DELAY)

    def brightness(self, val=None):
        """Set the display brightness 0-7."""
        if val is None:
            return self._brightness
        if not 0 <= val <= 7:
            raise ValueError("Brightness must be 0-7")
        self._brightness = val
        self._write_data_cmd()
        self._write_dsp_ctrl()

    def _write_data_cmd(self):
        self._start()
        self._write_byte(TM1637_CMD1)
        self._stop()

    def _write_dsp_ctrl(self):
        self._start()
        self._write_byte(TM1637_CMD3 | TM1637_DSP_ON | self._brightness)
        self._stop()

    def write(self, segments, pos=0):
        if not 0 <= pos <= 5:
            raise ValueError("Position must be 0-5")
        self._write_data_cmd()
        self._start()
        self._write_byte(TM1637_CMD2 | pos)
        for seg in segments:
            self._write_byte(seg)
        self._stop()
        self._write_dsp_ctrl()

    def encode_char(self, char):
        o = ord(char)
        if o == 32: # space
            return 0x00
        if 48 <= o <= 57: # 0-9
            return _SEGMENTS[o - 48]
        if 65 <= o <= 70: # A-F
            return _SEGMENTS[o - 55]
        if 97 <= o <= 102: # a-f
            return _SEGMENTS[o - 87]
        return 0x00 # unknown

    def encode_string(self, string):
        segments = bytearray(len(string))
        for i in range(len(string)):
            segments[i] = self.encode_char(string[i])
        return segments

    def number(self, num):
        """Display a number (-999 through 9999), right aligned."""
        num = max(-999, min(num, 9999))
        string = "{:>4}".format(num)
        self.write(self.encode_string(string))

    def numbers(self, num1, num2, colon=True):
        """Display two 2-digit numbers (0-99). Useful for clock."""
        num1 = max(-9, min(num1, 99))
        num2 = max(-9, min(num2, 99))
        
        # 1st number
        segments = [
            self.encode_char(str(num1 // 10)) if num1 >= 10 else 0,
            self.encode_char(str(num1 % 10))
        ]
        
        # 2nd number
        segments.append(self.encode_char(str(num2 // 10)) if num2 >= 10 else 0)
        segments.append(self.encode_char(str(num2 % 10)))
        
        if colon:
            segments[1] |= 0x80 # Turn on colon point
            
        self.write(segments)

    def show(self, string):
        """Display a string (len <= 4)."""
        if len(string) > 4:
            string = string[:4]
        self.write(self.encode_string(string))
