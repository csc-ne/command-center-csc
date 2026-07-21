import sys
import subprocess
import time
import webbrowser
import yaml
import requests
from tkinter.filedialog import askopenfilename
from utils.field_widget import FieldWidget
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import QIcon
from utils.check_auth import *
from utils.open_bat_files import *
from forms.customer import NewCustomerForm, EditCustomerForm
from forms.utils.modals.ModalAlert import *
from signals.Signals import AppSignals
from main import MessageShooter


class DashboardStatusChecker(QRunnable):
    def __init__(self) -> None:
        super().__init__()
        self.signals = AppSignals()
        self.healthy = True

    def run(self):
        while self.healthy:
            try:
                requests.get("http://localhost:8080")
                print("Dashboard OK!")
                time.sleep(300)
            except:
                self.healthy = False
                self.signals.dashboard_health.emit(0)


class Worker(QRunnable):
    def __init__(self):
        super(Worker, self).__init__()
        self.signals = AppSignals()

    @Slot()
    def run(self):
        # A verificação ocorre a cada 5s até o usuário se autenticar
        # no portal da John Deere
        for i in range(9999):
            if is_authenticate():
                self.signals.authenticate.emit(
                    True
                )  # Emite o sinal após estar autenticado
                return
            time.sleep(5)


class MainWindow(QMainWindow):
    alreadyDashboardOpened = False
    shooter_already_started = False

    def __init__(self):
        super().__init__()

        # Campos
        self.auth, self.dashboard, self.rts = (
            FieldWidget(button="Autenticar", group_box_name="1º Passo - Autenticação John Deere"),
            FieldWidget(button="Abrir Dashboard", group_box_name="2º Passo - RTS Dashboard"),
            FieldWidget(
                button="Ligar RTS",
                group_box_name="3º Passo - RTS Monitoramento de alertas",
                button2="Desligar RTS",
            ),
        )

        # Threading
        self.threadpool = QThreadPool()
        self.worker = Worker()
        self.shooter = MessageShooter()  # RTS
        self.checker = DashboardStatusChecker()

        # Signals

        ## Sinal de autenticação
        self.worker.signals.authenticate.connect(self.second_step)
        ## Sinal para cada alerta enviado
        self.shooter.signals.info_to_textbox.connect(self.capture_alert)
        ## Sinal para erros no monitoramento RTS
        self.shooter.signals.error_signal.connect(self.handle_error_rts)
        ## Sinal para erros no dashboard
        self.checker.signals.dashboard_health.connect(self.show_dashboard_error)
        ## Sinal para inatividade ao desligar o RTS
        self.shooter.signals.inactivity_detected.connect(self.show_inactivity_message)
        ## Sinal para atualizar o temporizador do RTS
        self.shooter.signals.time_to_update.connect(self.update_time)

        # Conexão do botão de autenticação
        self.auth.btn.clicked.connect(self.authentication)

        # Conexão do botão de abrir o dashboard
        self.dashboard.btn.clicked.connect(self.open_dashboard)

        # Conexão do botão de iniciar o RTS
        self.rts.btn.clicked.connect(self.turn_the_shooter_on)
        ## Conexão do botão auxiliar de desligar rts
        self.rts.btn2.clicked.connect(self.turn_the_shooter_off)

        if self.auth.situation.text() == "Desligado":
            self.dashboard.field.setEnabled(False)
            self.rts.field.setEnabled(False)


        # Prompt
        self.prompt_box = QTextEdit()
        self.prompt_box.setReadOnly(True)
        self.prompt_box.setTextInteractionFlags(Qt.NoTextInteraction)

        # Marcador de tempo
        self.time_field = QHBoxLayout()
        self.time_marker, time_label = QLabel(), QLabel()
        self.time_marker.setText("00:00")
        time_label.setText("Tempo restante para a próxima atualização:")
        self.time_field.addWidget(time_label)
        self.time_field.addWidget(self.time_marker)
        self.time_field.setContentsMargins(275, 0, 0, 0)

        layout = QVBoxLayout()
        layout.addWidget(self.auth.field)
        layout.addWidget(self.dashboard.field)
        layout.addWidget(self.rts.field)
        layout.addWidget(self.prompt_box)
        layout.addLayout(self.time_field)

        # Central Widget
        cw = QWidget()
        self.setCentralWidget(cw)
        cw.setLayout(layout)

        # Layout MainWindow
        self.setWindowTitle("Admin RTS")
        self.icon = QIcon()
        self.icon.addFile(r"interface\assets\computer.png")
        self.setWindowIcon(self.icon)

        # Menu de configurações
        opt = self.menuBar().addMenu("Configurações")

        ## Muda a cor ao passar o mouse no menu
        # opt.setStyleSheet("QMenu::item:selected {background-color: #222232;}")

        ## Menus inseridos em "Configurações"
        opt_db = opt.addMenu("Banco de dados")
        opt_db_customers = opt_db.addMenu("Clientes")
        opt_advanced = opt.addMenu("Opções avançadas...")

        ### Menu de configurações do monitor
        change_dashboard_file = opt_advanced.addAction("Alterar arquivo do dashboard")
        change_dashboard_file.triggered.connect(self.change_dir_files)

        ### Menu de configurações de clientes no BD
        add_customer = opt_db_customers.addAction("Adicionar")
        add_customer.triggered.connect(self.adding_customer)

        edit_customer = opt_db_customers.addAction("Editar")
        edit_customer.triggered.connect(self.editing_customer)

    def update_time(self, secs):
        # Converte de segundos para minutos
        timing = time.strftime("%M:%S", time.gmtime(secs))
        
        # Mostra na interface gráfica
        self.time_marker.setText(timing)
        

    def show_inactivity_message(self):
        """
        Após algum tempo com o RTS desligado, o programa
        irá desativar a opção de religar o RTS. Essa estratégia é para
        diminuir o uso de recursos do pc.
        """
        self.rts.handle_status("Desativado por inatividade")
        self.rts.field.setEnabled(False)

    def show_dashboard_error(self):
        # Abre a tela e mostra o aviso
        self.showNormal()
        self.activateWindow()

        self.dashboard.handle_status("Erro")

        CriticalAlertModal(
            title="Erro no Dashboard", message="Ocorreu algum erro com o Dashboard."
        )

    def change_dir_files(self):
        filename = askopenfilename(filetypes=[("Batch files", ".bat")])

        # Abre o arquivo de configuração
        with open(r"interface\configs\user.yml", "r") as file:
            cfg = yaml.load(file, Loader=yaml.FullLoader)
            # Pega a chave do diretório do arquivo e altera
            # para o valor filename
            cfg["userconfig"]["dashboard_bat_dir"] = filename

        # Abre o arquivo novamente e faz a alteração
        with open(r"interface\configs\user.yml", "w") as file:
            yaml.dump(cfg, file)

    def capture_alert(self, alert):
        """
        Insere o prompt de alerta na caixa de texto da interface
        do usuário
        """

        # Se a caixa estiver muito cheia, ele vai limpar.
        box_dim = len(self.prompt_box.toPlainText())
        if box_dim > 50000:
            self.prompt_box.clear()

        self.prompt_box.append(alert)

        if alert == "Desligamento automático devido ao encerramento do expediente":
            self.rts.handle_status("Desligado automaticamente")
            self.rts.field.setEnabled(False)

    def turn_the_shooter_on(self):
        """Inicia os disparos de mensagens"""

        # Necessário para não iniciar novamente o mesmo thread
        if not self.shooter_already_started:
            self.threadpool.start(self.shooter)
            self.shooter_already_started = True

        self.shooter.signals.status_rts_signal.emit("ON")

        self.rts.btn.setVisible(False)
        self.rts.btn2.setVisible(True)

        self.rts.handle_status("Online")

    def turn_the_shooter_off(self):
        """Desativa os disparos de mensagens"""
        self.shooter.signals.status_rts_signal.emit("OFF")
        self.rts.handle_status("Desligado")

        self.rts.btn.setVisible(True)
        self.rts.btn2.setVisible(False)

    def editing_customer(self):
        self.editForm = EditCustomerForm()
        self.editForm.show()

    def adding_customer(self):
        self.form = NewCustomerForm()
        self.form.show()

    def open_dashboard(self):
        
        # Checar se o servidor do dashboard já está ligado
        try:
            check_dashboard = requests.get("http://localhost:8080")
            
            if check_dashboard.status_code == 200:
                InfoAlertModal(
                    title="Dashboard iniciado.",
                    message="Acesse http://localhost:8080"
                )
                self.threadpool.start(self.checker)  # Verifica a saúde do dashboard ao longo do dia
                self.dashboard.handle_status("OK")

                self.dashboard.field.setEnabled(False)
                self.rts.field.setEnabled(True)

                return
        
        # Se der erro, ele vai considerar que o dashboard não está ligado
        # e vai seguir o código abaixo
        except:  
            pass

        try:
            # Abre as configurações e pega o diretório do arquivo
            with open(r"interface\configs\user.yml", "r") as file:
                cfg = yaml.load(file, Loader=yaml.FullLoader)
                filepath = cfg["userconfig"]["dashboard_bat_dir"]

            # Verifica se o diretório do batch file está correto
            if filepath[len(filepath) - 4 : len(filepath)] != ".bat":
                WarningAlertModal(
                    title="Não foi possível iniciar o dashboard",
                    message="Verifique o diretório do arquivo .bat de inicialização",
                )
                return

            self.threadpool.start(self.checker)

            url = "http://localhost:8080"

            # Inicializa o servidor do dashboard
            initialize_resource(url, filepath, subprocess.CREATE_NEW_CONSOLE)

            self.dashboard.handle_status("OK")
            self.rts.field.setEnabled(True)

            self.alreadyDashboardOpened = True  # Registra que o botão já foi clicado

            self.dashboard.field.setEnabled(False)
        except Exception as e:
            raise Exception(f"Não foi possível abrir o dashboard: {e}")

    def authentication(self):
        """
        Essa função só funciona se o usuário já tem estabelecido o fluxo
        OAuth2 exigido pela John Deere.

        O código de autenticação é obtido utilizando um servidor intermediário
        de autorização entre o "client" e "resource owner"
        """

        url = "http://localhost:5000/"

        # Para não iniciar o mesmo Thread caso já tenha iniciado
        if self.auth.situation.text() == "Aguardando":
            webbrowser.get(using=None).open(url)
            return

        # Verifica se o usuário já está autenticado com a John Deere
        try:
            if not is_authenticate():
                webbrowser.get(using=None).open(url)
            else:
                # Se já estiver autenticado, o usuário já vai para o próximo passo
                self.second_step()
                return

        except:
            # Mostra erro no monitor
            self.auth.handle_status("Erro")

            CriticalAlertModal(
                title="Erro", message="Não foi possível efetuar a autenticação"
            )

            return

        # Mostra status de aguardando autenticação
        self.auth.handle_status("Aguardando")

        # Inicia a verificação de autenticação
        self.threadpool.start(self.worker)

    def second_step(self):
        # Após autenticar
        InfoAlertModal(
            title="Autenticado", message="A autenticação foi efetuada com sucesso."
        )

        # Ativa o botão do dashboard e desativa o botão de autenticação
        self.dashboard.field.setEnabled(True)
        self.auth.field.setEnabled(False)

        return self.auth.handle_status("OK")

    def handle_error_rts(self, error):
        # Abre a tela e mostra o aviso
        self.showNormal()
        self.activateWindow()

        CriticalAlertModal(title="Erro no envio de alertas", message=error)

        self.rts.handle_status("Erro")
        self.rts.field.setEnabled(False)


if __name__ == "__main__":
    app = QApplication([])

    widget = MainWindow()
    widget.resize(550, 500)
    widget.show()

    sys.exit(app.exec())
