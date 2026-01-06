import machine
try:
    from . import ssd1306
except ImportError:
    import ssd1306

class OLEDManager:
    """
    OLED 显示管理类 (Display Manager)
    封装了 SSD1306 的初始化与绘图操作，提供更易用的接口。
    """
    def __init__(self, scl_pin=22, sda_pin=21, width=128, height=64):
        self.scl_pin = scl_pin
        self.sda_pin = sda_pin
        self.width = width
        self.height = height
        self.oled = None
        self.i2c = None

    def init_display(self):
        """硬件初始化：配置 I2C 并实例化 SSD1306 驱动"""
        try:
            self.i2c = machine.SoftI2C(scl=machine.Pin(self.scl_pin), sda=machine.Pin(self.sda_pin))
            self.oled = ssd1306.SSD1306_I2C(self.width, self.height, self.i2c)
            return True
        except Exception as e:
            print(f"[显示] OLED 初始化失败: {e}")
            return False

    def clear(self, show=False):
        """清空显存"""
        if self.oled:
            self.oled.fill(0)
            if show:
                self.oled.show()

    def show_text(self, text, x=0, y=0, clear_first=True):
        """
        显示文本
        :param text: 要显示的字符串 (仅支持 ASCII 英文/数字)
        :param clear_first: 是否先清除屏幕(全屏清除)
        """
        if not self.oled:
            return
        if clear_first:
            self.oled.fill(0)
        self.oled.text(text, x, y)
        self.oled.show()

    def draw_box(self, x=0, y=0, w=128, h=64, border=1):
        """绘制矩形框"""
        if not self.oled:
            return
        self.oled.rect(x, y, w, h, border)
        self.oled.show()
