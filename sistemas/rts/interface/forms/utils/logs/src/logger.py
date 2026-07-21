"""
RTS — InterfaceLogger
Logger de erros da camada de formulários da interface PySide6.
"""

import os
import traceback
from datetime import datetime


_LOG_DIR = os.path.join(
    os.path.dirname(__file__),   # logs/src/
    "..",                         # logs/
    "..",                         # utils/
    "..",                         # forms/
    "..",                         # interface/
    "..",                         # RTS root
    "logs", "output"
)


class InterfaceLogger:
    """
    Logger de erros para os formulários da interface.

    Uso:
        InterfaceLogger(error_text=err)

    Grava a exceção completa (com traceback) no arquivo de log de erros do dia,
    no mesmo diretório de logs do sistema (logs/output/).
    """

    def __init__(self, error_text: Exception = None):
        log_dir = os.path.normpath(_LOG_DIR)
        os.makedirs(log_dir, exist_ok=True)

        if error_text is not None:
            self._write_error(log_dir, error_text)

    def _write_error(self, log_dir: str, err: Exception):
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(log_dir, f"interface_errors_{date_str}.log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb = traceback.format_exc()
        content = f"[{timestamp}] InterfaceLogger — {type(err).__name__}: {err}\n{tb}\n"
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            print(f"[InterfaceLogger] Falha ao gravar log: {e}")
            print(content)
