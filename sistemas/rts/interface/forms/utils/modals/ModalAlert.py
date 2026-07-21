import sys
from PySide6.QtWidgets import *
from PySide6.QtGui import *

class ModalWindow:
    def __init__(self, title: str, message: str, icon: QIcon):
        self.title = title
        self.message = message
        self.icon = icon

        icon = QIcon()
        icon.addFile(r"interface\forms\icons\warning.png")

        self.msgbox = QMessageBox()
        self.msgbox.setWindowTitle(self.title)
        self.msgbox.setWindowIcon(self.icon)
        self.msgbox.setText(self.message)
        self.msgbox.exec()


class WarningAlertModal:
    def __init__(self, title: str, message: str) -> None:
        icon = QIcon()
        icon.addFile(r"interface\forms\icons\warning.png")

        ModalWindow(title=title, message=message, icon=icon)


class CriticalAlertModal:
    def __init__(self, title: str, message: str):
        icon = QIcon()
        icon.addFile(r"interface\forms\icons\critical.png")

        ModalWindow(title=title, message=message, icon=icon)

class InfoAlertModal:
    def __init__(self, title: str, message: str):
        icon = QIcon()
        icon.addFile(r"interface\forms\icons\info.png")

        ModalWindow(title=title, message=message, icon=icon)

class ConfirmationModal:
    def __init__(self, title: str, message: str):
        icon = QIcon()
        icon.addFile(r"interface\forms\icons\warning.png")
        
        # Captura a escolha do usuário
        self.confirmation: bool

        # Instância
        self.dlg = QDialog()

        # Configurações visuais
        self.dlg.setWindowTitle(title)
        self.dlg.setWindowIcon(icon)
        self.dlg.resize(100, 80)

        # Layout Principal
        main_layout = QVBoxLayout()
        
        # Mensagem do dialog
        msg_label = QLabel(message)

        # Área dos botões
        btns_layout = QHBoxLayout()
        self.btn_yes = QPushButton("Sim")
        self.btn_no = QPushButton("Não")

        # Conexão dos botões com os métodos da classe
        # Necessário para capturar as ações dos botões
        self.btn_yes.clicked.connect(self.accepted)
        self.btn_no.clicked.connect(self.rejected)

        ## Adição dos botões ao layout dos botões
        btns_layout.addWidget(self.btn_yes)
        btns_layout.addWidget(self.btn_no)
        
        # Adição dos componentes ao layout principal
        main_layout.addWidget(msg_label)
        main_layout.addLayout(btns_layout)

        self.dlg.setLayout(main_layout)
        self.dlg.exec()

    def accepted(self):
        self.confirmation = True
        self.dlg.close()
    
    def rejected(self):
        self.confirmation = False
        self.dlg.close()

        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    InfoAlertModal(title="Teste", message="Teste")
    