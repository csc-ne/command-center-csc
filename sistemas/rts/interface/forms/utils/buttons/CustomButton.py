import sys
from PySide6.QtGui import *
from PySide6.QtWidgets import *

class ButtonComponent(QPushButton):
    def __init__(self, buttonName: str, color: str, icon: str):
        super().__init__()
        self.setText(buttonName)
        self.setMaximumWidth(170)
        self.setStyleSheet(
            f"background-color: {color}; color: white; font-weight: bold;"
        )
        self.icon_btn = QIcon()
        self.icon_btn.addFile(icon)
        self.setIcon(self.icon_btn)


class WindowTest(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        btn = ButtonComponent(
            buttonName="Pesquisar",
            color="green",
            icon=r"interface\forms\icons\search.png",
        )
        
        layout.addWidget(btn)

        self.setLayout(layout)
        self.resize(100, 100)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = WindowTest()
    win.show()
    app.exec()
