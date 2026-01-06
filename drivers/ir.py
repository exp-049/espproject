import machine

class IRManager:
    def __init__(self, pin=35):
        self.pin = machine.Pin(pin, machine.Pin.IN)

    def read_state(self):
        """Returns 0 or 1"""
        try:
            return self.pin.value()
        except Exception as e:
            print(f"[IR] Error: {e}")
            return -1
