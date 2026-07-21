import subprocess
import webbrowser
from subprocess import Popen


def initialize_resource(
    url: str, filepath: str, flag = subprocess.CREATE_NEW_CONSOLE
):
    """
    Executa o arquivo .bat e abre uma página no navegador.

    Arquivos .bat precisam ser executados via cmd.exe no Windows —
    Popen([arquivo.bat]) sozinho causa FileNotFoundError (WinError 2).
    """
    p = Popen(["cmd", "/c", filepath], creationflags=flag)

    # Abre a página no navegador
    webbrowser.get(using=None).open(url)

    return p
