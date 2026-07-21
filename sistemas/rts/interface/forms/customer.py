import sys
from PySide6.QtWidgets import *
from PySide6.QtGui import QIcon, QDoubleValidator

from forms.utils.modals.ModalAlert import *
from forms.utils.modals.ModalTable import TableCustomers
from forms.utils.logs.src.logger import InterfaceLogger
from forms.utils.buttons.CustomButton import ButtonComponent
sys.path.append("./")  # Necessário para o módulo rodar no app
from BD_alertas import BancoDados


class NewCustomerForm(QWidget):
    def __init__(self):
        super().__init__()

        # Conexão com o Banco de Dados
        self.db = BancoDados(nome_tabela="contatos")

        # Campos de preenchimento
        l1 = QLabel("Cliente")
        self.customer = QLineEdit()

        l2 = QLabel("ID da Organização (Operations Center)")
        self.id_customer = QLineEdit()

        l3 = QLabel("Estado (sigla)")
        self.uf = QLineEdit()
        self.uf.setMaxLength(2)

        l4 = QLabel("Responsável")
        self.responsible = QLineEdit()

        l5 = QLabel("Telefone")
        self.phone_number = QLineEdit()
        self.phone_number.setMaxLength(11)
        self.phone_number.setValidator(QDoubleValidator())  # only numbers

        l6 = QLabel("Email")
        self.email = QLineEdit()

        l7 = QLabel("CEN")
        self.cen = QLineEdit()

        # Layout do formulário
        form = QFormLayout()

        # Botão
        btn_add_customer = QPushButton("Adicionar")
        btn_add_customer.clicked.connect(self.add_customer)

        # Adição dos campos
        form.addRow(l1, self.customer)
        form.addRow(l2, self.id_customer)
        form.addRow(l3, self.uf)
        form.addRow(l4, self.responsible)
        form.addRow(l5, self.phone_number)
        form.addRow(l6, self.email)
        form.addRow(l7, self.cen)
        form.addWidget(btn_add_customer)

        # Janela
        self.setWindowTitle("Adicionar cliente")
        self.setLayout(form)
        self.resize(500, 200)

        ## Ícone da janela
        self.icon = QIcon()
        self.icon.addFile(r"interface\forms\icons\add-user.png")
        self.setWindowIcon(self.icon)

    def add_customer(self):
        # Checagem se os campos estão vazios
        if (
            (not self.uf.text())
            or (not self.customer.text())
            or (not self.responsible.text())
            or (not self.phone_number.text())
            or (not self.email.text())
            or (not self.cen.text())
            or (not self.id_customer.text())
        ):
            WarningAlertModal(
                title="Aviso", message="Todos os campos devem ser preenchidos."
            )

            return

        try:
            self.db.incluir_cliente(
                uf=self.uf.text(),
                cliente=self.customer.text(),
                responsavel=self.responsible.text(),
                telefone=self.phone_number.text(),
                email=self.email.text(),
                cen=self.cen.text(),
                idCliente=self.id_customer.text(),
            )

            print("Customer info submitted successfully")

            InfoAlertModal(title="Informação", message="Informações salvas.")

        except Exception as err:
            # Logs
            InterfaceLogger(error_text=err)

            # Janela de erro
            CriticalAlertModal(
                title="Erro de cadastro",
                message="Não foi possível salvar o cadastro do cliente",
            )


class EditCustomerForm(QWidget):
    def __init__(self):
        super().__init__()

        # Instanciando o banco de dados
        self.db = BancoDados(nome_tabela="contatos")

        # Coletando os nomes das colunas
        self.header = self.db.capture_columns()

        # Campo de pesquisa
        search_field = QVBoxLayout()
        search_field.addStretch(1)  # Não expande quando a janela expande
        search_box = QGroupBox("Pesquisar por")

        ## Campos de preenchimento de pesquisa
        l1 = QLabel("Nome do cliente")
        self.t1 = QLineEdit()

        l2 = QLabel("ID da Organização")
        self.t2 = QLineEdit()

        l3 = QLabel("Telefone")
        self.t3 = QLineEdit()

        ### Condição para a entrada de ID e telefone permitir apenas números
        self.t2.setValidator(QDoubleValidator())
        self.t3.setValidator(QDoubleValidator())

        ### Formato de telefone (99) 9 9999-9999
        self.t3.setInputMask("(99) 9 9999-9999")

        # Botão de pesquisar o cliente no banco de dados
        search_button = ButtonComponent(
            buttonName="Pesquisar",
            color="green",
            icon=r"interface\forms\icons\search.png",
        )
        search_button.clicked.connect(self.search_customer)

        ## Adição dos widgets de pesquisa
        search_field.addWidget(l1)
        search_field.addWidget(self.t1)
        search_field.addWidget(l2)
        search_field.addWidget(self.t2)
        search_field.addWidget(l3)
        search_field.addWidget(self.t3)
        search_field.addWidget(search_button)

        ## Layout do campo de pesquisa
        search_box.setLayout(search_field)

        # Campo de Resultado
        info_box = QGroupBox("Resultado")

        ## Componentes
        (
            self.name,
            self.id,
            self.uf,
            self.responsible,
            self.phone,
            self.email,
            self.cen,
        ) = (
            InfoBox("Cliente"),
            InfoBox("ID da Organização"),
            InfoBox("Estado"),
            InfoBox("Responsável"),
            InfoBox("Telefone"),
            InfoBox("Email"),
            InfoBox("CEN"),
        )

        # Botão de edição
        self.edit_btn = ButtonComponent(
            buttonName="Editar", color="blue", icon=r"interface\forms\icons\pencil.png"
        )
        self.edit_btn.clicked.connect(self.edit_customer)

        # Botão de remoção
        self.remove_btn = ButtonComponent(
            buttonName="Remover", color="red", icon=r"interface\forms\icons\delete.png"
        )
        self.remove_btn.setVisible(False)
        self.remove_btn.clicked.connect(self.remove_customer)

        # Botão de salvar informações
        self.submit_btn = ButtonComponent(
            buttonName="Salvar Informações",
            color="green",
            icon=r"interface\forms\icons\check-mark.png",
        )
        self.submit_btn.clicked.connect(self.submit_infos)
        self.submit_btn.setVisible(False)

        # Box de resultado
        result_box = QVBoxLayout()

        ## Box 1 - Cliente, Responsável e ID
        box1 = QHBoxLayout()
        box1.addLayout(self.name.field)
        ### Tamanhos das caixas de texto
        self.id.lineEdit.setMaximumWidth(100)
        self.cen.lineEdit.setMaximumWidth(100)
        box1.addLayout(self.id.field)
        box1.addLayout(self.cen.field)
        result_box.addLayout(box1)

        ## Box 2 - Estado, telefone e CEN
        box2 = QHBoxLayout()
        box2.addLayout(self.uf.field)
        box2.addLayout(self.phone.field)
        ### Tamanhos das caixas de texto
        self.responsible.lineEdit.setMaximumWidth(150)
        box2.addLayout(self.responsible.field)
        result_box.addLayout(box2)

        # Box 3 - Email
        result_box.addLayout(self.email.field)

        ## Botões de edição
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.submit_btn)
        result_box.addLayout(btn_layout)

        ## Identificador
        identifier_layout = QHBoxLayout()
        identifier_label = QLabel()
        identifier_label.setText("Identificador")
        identifier_label.setStyleSheet(
            "font-style: italic; font-size: 10px; color: gray"
        )
        self.identifier_number = QLabel()
        self.identifier_number.setText("0")
        self.identifier_number.setStyleSheet(
            "font-style: italic; font-size: 10px; color: grey"
        )
        identifier_layout.addWidget(identifier_label)
        identifier_layout.addWidget(self.identifier_number)
        identifier_layout.addStretch()  # Remove espaços entre labels
        result_box.addLayout(identifier_layout)

        ## Setando o layout dos resultados
        info_box.setLayout(result_box)

        # Janela
        window_layout = QVBoxLayout()
        window_layout.addWidget(search_box)
        window_layout.addWidget(info_box)

        ## Ícone
        self.icon = QIcon()
        self.icon.addFile(r"interface\forms\icons\edit-user.png")
        self.setWindowIcon(self.icon)
        self.setLayout(window_layout)
        self.setWindowTitle("Edição de cliente")
        self.resize(700, 300)

    def remove_customer(self):
        user_choice = ConfirmationModal(
            title="Confirmação",
            message="Este cliente será excluído. Deseja continuar?",
        )

        identifier_db = self.identifier_number.text()

        if user_choice.confirmation == True:
            try:
                self.db.excluir_cliente(identifier_db)
                
                # As informações são apagadas da interface após exclusão
                self.identifier_number.setText("")
                self.uf.lineEdit.setText("")
                self.name.lineEdit.setText("")
                self.id.lineEdit.setText("")
                self.responsible.lineEdit.setText("")
                self.phone.lineEdit.setText("")
                self.email.lineEdit.setText("")
                self.cen.lineEdit.setText("")

                self.controller_search_results_fields(False)

                InfoAlertModal(
                    title="Exclusão efetuada",
                    message="O cliente foi excluído."
                )
                
            except:
                CriticalAlertModal(
                    title="Erro",
                    message="Não foi possível excluir o cliente."
                )

                return
        else:
            print("O cliente não foi excluído")
            
        

    def edit_customer(self):
        # Caso clique no botão de edição antes da hora
        if len(self.name.lineEdit.text()) == 0:
            WarningAlertModal(
                title="Aviso", message="Selecione um cliente antes de editar"
            )
            return

        # Ativa a edição dos campos de info do cliente
        self.controller_search_results_fields(True)

        # Esconde o botão de edição e mostra os botões de salvar/remover
        self.edit_btn.setVisible(False)
        self.remove_btn.setVisible(True)
        self.submit_btn.setVisible(True)

    def submit_infos(self):
        """Armazena as informações editadas"""
        try:
            self.db.atualizar_cliente(
                uf=self.uf.lineEdit.text(),
                cliente=self.name.lineEdit.text(),
                id_org=self.id.lineEdit.text(),
                responsavel=self.responsible.lineEdit.text(),
                telefone=self.phone.lineEdit.text(),
                email=self.email.lineEdit.text(),
                cen=self.cen.lineEdit.text(),
                identificador=self.identifier_number.text(),
            )

            # Desativa os campos de busca após a atualização
            # dos cadastros
            self.controller_search_results_fields(False)

            self.edit_btn.setVisible(True)
            self.remove_btn.setVisible(False)
            self.submit_btn.setVisible(False)

            InfoAlertModal(title="Aviso", message="Informações submetidas com sucesso")

            print("Information submitted")

        except Exception as err:
            # Logs
            InterfaceLogger(error_text=err)

            # Janela de erro
            CriticalAlertModal(
                title="Erro", message="Não foi possível submeter as informações"
            )

    def search_customer(self):
        # Limpando formatação do inputMask
        extract_phone = [i for i in self.t3.text() if i.isdigit()]
        phone_formatted = "".join(extract_phone)

        result_db = self.db.consultar_cliente(
            cliente=self.t1.text(),
            id_org=self.t2.text(),
            telefone=phone_formatted,
        )

        if len(result_db) > 1:

            # Mostra as opções encontradas em formato de tabela
            results = TableCustomers(data_list=result_db, header=self.header)
            results.exec()

            final_result = results.customer_selected

        elif len(result_db) == 0:
            WarningAlertModal(title="Aviso", message="Nenhum resultado encontrado")

            return

        else:  # Se encontrar apenas um resultado
            final_result = result_db[0]

        # Coloca os dados encontrados no banco de dados na interface
        self.identifier_number.setText(
            str(final_result[0])
        )  # O número vem como int do BD
        self.uf.lineEdit.setText(final_result[1])
        self.name.lineEdit.setText(final_result[2])
        self.id.lineEdit.setText(final_result[3])
        self.responsible.lineEdit.setText(final_result[4])
        self.phone.lineEdit.setText(final_result[5])
        self.email.lineEdit.setText(final_result[6])
        self.cen.lineEdit.setText(final_result[7])

    def controller_search_results_fields(self, command: bool):
        """False: desativa a modificação do campo por parte do usuário.

        True: ativa a modificação do campo por parte do usuário
        """
        
        # Ativa a edição dos campos de info do cliente
        self.uf.lineEdit.setEnabled(command)
        self.name.lineEdit.setEnabled(command)
        self.id.lineEdit.setEnabled(command)
        self.responsible.lineEdit.setEnabled(command)
        self.phone.lineEdit.setEnabled(command)
        self.email.lineEdit.setEnabled(command)
        self.cen.lineEdit.setEnabled(command)


class InfoBox(QWidget):
    def __init__(self, lbl: str) -> None:
        super().__init__()

        self.field = QVBoxLayout()
        self.label = QLabel(lbl)
        self.lineEdit = QLineEdit()
        self.lineEdit.setEnabled(False)

        self.field.addWidget(self.label)
        self.field.addWidget(self.lineEdit)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = EditCustomerForm()
    widget.show()
    sys.exit(app.exec())
