import sys
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *

# Necessário para pegar os componentes
sys.path.append("./interface/forms/utils")
from modals.ModalAlert import WarningAlertModal
from buttons.CustomButton import ButtonComponent


class TableCustomers(QDialog):
    def __init__(self, data_list: list, header: list, *args):
        QDialog.__init__(self, *args)

        # Para salvar o cliente selecionado
        self.customer_selected = []

        # Configuração da janela
        self.setWindowTitle("Clientes encontrados")
        self.resize(800, 300)

        ## Ícone da janela
        icon = QIcon()
        icon.addFile(r"interface\forms\icons\edit-user.png")
        self.setWindowIcon(icon)

        # Tabela
        self.table_model = TableModel(self, data_list, header)
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)

        # Selecionar a linha inteira ao clicar
        self.table_view.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        ## Configuração da tabela
        font = QFont("Verdana", 8)
        self.table_view.setFont(font)

        ### Ajuste do tamanho da coluna
        self.table_view.resizeColumnsToContents()

        ## Botão de selecionar
        select_btn = ButtonComponent(
            buttonName="Selecionar",
            color="DarkCyan",
            icon=r'interface\forms\icons\check-mark.png'
        )

        select_btn.clicked.connect(self.customer_selection)

        layout = QVBoxLayout(self)
        layout.addWidget(self.table_view)
        layout.addWidget(select_btn)
        self.setLayout(layout)

        

    def customer_selection(self):
        # Pega a seleção do usuário
        selection = self.table_view.selectedIndexes()

        # Caso o usuário selecione mais de 1 cliente
        if len(selection) > self.table_model.columnCount(self):
            WarningAlertModal(
                title="Aviso", message="Você só pode selecionar um cliente."
            )

            return
        
        # Ou caso não selecione nenhum cliente
        elif len(selection) == 0:
            WarningAlertModal(
                title="Aviso",
                message="Nenhum cliente selecionado."
            )

            return

        # Itera sobre cada célula da linha escolhida
        for cell in selection:
            self.customer_selected.append(cell.data())

        # Fecha a tabela
        self.close()

        return self.customer_selected


class TableModel(QAbstractTableModel):
    def __init__(self, parent, mylist, header, *args):
        QAbstractTableModel.__init__(self, parent, *args)
        self.mylist = mylist
        self.header = header

    def rowCount(self, parent):
        return len(self.mylist)

    def columnCount(self, parent):
        return len(self.mylist[0])

    def data(self, index, role):
        if not index.isValid():
            return None
        elif role != Qt.DisplayRole:
            return None
        return self.mylist[index.row()][index.column()]

    def headerData(self, col, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.header[col]
        return None


if __name__ == "__main__":
    # Cabeçalho da tabela
    header = [
        "Identificador",
        "UF",
        "Cliente",
        "JDLink_ID",
        "Responsável",
        "Telefone",
        "Email",
        "CEN",
    ]

    data_list = [
        (
            1,
            "A",
            "B",
            "C",
            "D",
            "E",
            "F@gmail.com",
            "G",
        ),
        (
            389,
            "H",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O",
        ),
        (
            403,
            "P",
            "Q",
            "R",
            "S",
            "T",
            "U@hotmail.com",
            "V",
        ),
    ]
    
    QApplication([])

    win = TableCustomers(data_list, header)
    win.exec()

    print(win.customer_selected)
