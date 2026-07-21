from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
    QLabel,
    QHBoxLayout,
    QGroupBox,
)

class FieldWidget(QWidget):
    def __init__(self, button: str, group_box_name: str, button2: str = None):
        # Botão
        self.btn = QPushButton(button)

        # Status
        status_label, self.situation = QLabel(), QLabel()
        status_label.setText("Status")
        self.situation.setText("Desligado")

        self.situation.setStyleSheet("color: gray; font-weight: bold")

        ## Status Box
        status_box = QHBoxLayout()
        status_box.addWidget(status_label)
        status_box.addWidget(self.situation)

        # Layout do Box
        self.layoutBox = QHBoxLayout()
        self.layoutBox.addWidget(self.btn)
        ## Botão auxiliar
        if button2 != None:
            self.btn2 = QPushButton(button2)
            self.layoutBox.addWidget(self.btn2)
            self.btn2.setVisible(False)

        self.layoutBox.addWidget(status_label)
        self.layoutBox.addWidget(self.situation)
        

        self.field = QGroupBox(group_box_name)
        
        self.field.setLayout(self.layoutBox)
        # self.field.setStyleSheet("color: white")
    
    def handle_status(self, status: str):
        match status.upper():
            case "DESLIGADO":
                self.situation.setText(status)
                self.situation.setStyleSheet("color: gray; font-weight: bold")
            case "AGUARDANDO" | "DESATIVADO POR INATIVIDADE":
                self.situation.setText(status)
                self.situation.setStyleSheet("color: orange; font-weight: bold")
            case "OK" | "ONLINE":
                self.situation.setText(status)
                self.situation.setStyleSheet("color: green; font-weight: bold")
            case "ERRO":
                self.situation.setText(status)
                self.situation.setStyleSheet("color: red; font-weight: bold")
            case "DESLIGADO AUTOMATICAMENTE":
                self.situation.setText(status)
                self.situation.setStyleSheet("color: blue; font-weight: bold")


