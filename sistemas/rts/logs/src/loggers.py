"""
RTS — Logger Module
Registra erros e eventos do sistema em arquivos de log datados.
"""

import os
import traceback
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "output")


class Logger:
    """
    Logger central do RTS.

    Métodos:
        error_logger(err)  — grava exceção completa no arquivo de log de erros
        info_logger(msg)   — grava mensagem informativa no log geral
    """

    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)

    def _log_file(self, prefix: str) -> str:
        date_str = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(LOG_DIR, f"{prefix}_{date_str}.log")

    def _write(self, filepath: str, content: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {content}\n")
        except OSError as e:
            # Fallback: imprime no console se não conseguir gravar no arquivo
            print(f"[Logger] Falha ao gravar log: {e}")
            print(f"[{timestamp}] {content}")

    def error_logger(self, err: Exception):
        """Grava exceção completa (traceback) no log de erros do dia."""
        tb = traceback.format_exc()
        content = f"ERROR — {type(err).__name__}: {err}\n{tb}"
        self._write(self._log_file("errors"), content)

    def info_logger(self, msg: str):
        """Grava mensagem informativa no log geral do dia."""
        self._write(self._log_file("info"), msg)
