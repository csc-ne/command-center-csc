# =======================================================================
# VENEZA EQUIPAMENTOS SA
# CENTRO DE SOLUCOES CONECTADAS - CSC
# REPORT AUTOMATICO DE DESEMPENHO - RAD
# DESENVOLVIDO POR THIAGO BARROS - thiago.barros@venezanet.com - 2026.1
# VERSÃO ESTÁVEL - 0.2.6.4 - Data 04/06/2026 - Fluxo Contínuo Funcional
# =======================================================================
# Revisão - 0.1 - 19/02/2026 - Criação das Bibliotecas de Interação Com os Dados - kernel
# Revisão - 0.1 - 19/02/2026 - Criação das Bibliotecas de Geração de PDF
#
# Acesso ao Banco
#======================

# Módulo de Execução - Acesso ao Banco

import psycopg2
import pandas as pd
import threading
from psycopg2 import OperationalError
from kernel.modulo_banco import Config


class BancoService:

    def __init__(self):

        self.conn = None
        # Thread-local storage para conexões paralelas
        self._local = threading.local()

    # ----------------------------------------------
    # Conexão com o Banco (thread-safe)
    # ----------------------------------------------

    def _get_conn(self):
        """Retorna a conexão da thread atual, criando uma nova se necessário."""
        conn = getattr(self._local, 'conn', None)
        if conn is None or conn.closed != 0:
            try:
                conn = psycopg2.connect(
                    host=Config.PG_HOST,
                    port=Config.PG_PORT,
                    dbname=Config.PG_DB,
                    user=Config.PG_USER,
                    password=Config.PG_PASS,
                )
                self._local.conn = conn
            except OperationalError as erro:
                print(f'Verifique credenciais do banco Interno {erro}')
                return None
        return conn

    def conectar(self):

        if self.conn is None or self.conn.closed != 0:

            try:


                self.conn = psycopg2.connect(

                    host = Config.PG_HOST,
                    port = Config.PG_PORT,
                    dbname = Config.PG_DB,
                    user = Config.PG_USER,
                    password = Config.PG_PASS

                )

            except OperationalError as erro:

                print(f'Verifique credenciais do banco Interno {erro}')
                return False

    # ---------------------------------------------
    # Método para Testar Conexão no Banco
    # ---------------------------------------------

    def testar_conexao(self):

        try:

            self.conectar()
            cur = self.conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()

            return True

        except Exception:

            return False

    # ---------------------------------------------
    # Método para Execução de Consulta no Banco
    # ---------------------------------------------

    def executar(self, query: str, params=None):

        # Usa conexão thread-local quando chamado de uma thread paralela,
        # caso contrário usa a conexão principal (compatibilidade legado).
        _is_worker = threading.current_thread() is not threading.main_thread()
        if _is_worker:
            conn = self._get_conn()
            if conn is None:
                raise RuntimeError("Falha ao obter conexão com o banco (thread worker)")
        else:
            self.conectar()
            conn = self.conn

        try:

            cur = conn.cursor()
            is_select = query.strip().lower().startswith("select")
            is_with = query.strip().lower().startswith("with")
            cur.execute(query, params)

            if is_select or is_with:

                dados = cur.fetchall()
                colunas = [desc[0] for desc in cur.description]
                cur.close()
                return pd.DataFrame(dados, columns=colunas)

            else:

                print('Só é permitido realizar consultas no banco com SELECT ou WITH para CTE')
                return None


        except Exception as e:

            conn.rollback()
            raise RuntimeError(f"Erro ao executar SQL: {e}")

    # -------------------------------------------
    # Fechar Conexão
    # -------------------------------------------

    def desconectar(self):

        if self.conn and self.conn.closed == 0:
            
            self.conn.close()
            self.conn = None
