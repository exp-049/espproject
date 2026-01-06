import machine
try:
    from . import ssd1306
except ImportError:
    import ssd1306

class OLEDManager:
    def __init__(self, scl_pin=22, sda_pin=21, width=128, height=64):
        self.scl_pin = scl_pin
        self.sda_pin = sda_pin
        self.width = width
        self.height = height
        self.oled = None
        self.i2c = None

    def init_display(self):
        """Hardware initialization"""
        try:
            self.i2c = machine.SoftI2C(scl=machine.Pin(self.scl_pin), sda=machine.Pin(self.sda_pin))
            self.oled = ssd1306.SSD1306_I2C(self.width, self.height, self.i2c)
            return True
        except Exception as e:
            print(f"[OLED] Init Error: {e}")
            return False

    def clear(self, show=False):
        if self.oled:
            self.oled.fill(0)
            if show:
                self.oled.show()

    def show_text(self, text, x=0, y=0, clear_first=True):
        if not self.oled:
            return
        if clear_first:
            self.oled.fill(0)
        self.oled.text(text, x, y)
        self.oled.show()

    def draw_box(self, x=0, y=0, w=128, h=64, border=1):
        if not self.oled:
            return
        self.oled.rect(x, y, w, h, border)
        self.oled.show()
