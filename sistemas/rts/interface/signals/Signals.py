from PySide6.QtCore import *


class AppSignals(QObject):
    dashboard_health = Signal(int)
    time_to_update = Signal(int)
    authenticate = Signal(bool)
    info_to_textbox = Signal(str)
    status_rts_signal = Signal(str)
    status_rts = "ON"
    inactivity_detected = Signal(bool)

    error_signal = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.status_rts_signal.connect(self.rts_activation_control)

    def rts_activation_control(self, status):
        if status == "ON":
            self.status_rts = "ON"
        else:
            self.status_rts = "OFF"
