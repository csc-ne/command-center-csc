"""
BD_alertas.py — Camada de acesso a dados do RTS (PostgreSQL)
=============================================================

Migrado de mysql.connector para psycopg2.
Banco: csc_veneza (PostgreSQL 192.168.0.106:5432)

Tabelas PG:
    rts_alertas        (antes: bancovz.Alertas)
    rts_contatos       (antes: bancovz.contatos)
    rts_runtime_config (antes: bancovz.runtime_config)

Mapeamento de nomes: o construtor de BancoDados continua recebendo
nomes lógicos ("Alertas", "contatos", "runtime_config") para
manter compatibilidade com callers existentes. O mapeamento para
o nome real da tabela PG é feito internamente via _TABLE_MAP.

Contratos preservados:
    - bd.cursor e bd.cnx continuam acessíveis (usados por
      runtime_config.py, batch_alert_sender.py, etc.)
    - executar_DML(comando, valores) e executar_DQL(comando) mantêm
      a mesma assinatura.
    - incluir() agora aceita campos adicionais opcionais:
      notification_id, color_id, severity, three_letter_acronym,
      machine_model (para a migração de fonte API → PG).
"""

import psycopg2
from dotenv import load_dotenv
import os, platform

# .env centralizado em C:\env\.env no host Windows.
# No container Linux, o docker-compose monta esse arquivo em /app/.env.
_ENV_PATH = r"C:\env\.env" if platform.system() == "Windows" else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)

# ── Mapeamento de nomes lógicos → tabelas PG ──────────────────
_TABLE_MAP = {
    "alertas":        "rts_alertas",
    "contatos":       "rts_contatos",
    "runtime_config": "rts_runtime_config",
}


def _resolve_table(nome_tabela: str) -> str:
    """Converte nome lógico (case-insensitive) para nome real PG."""
    return _TABLE_MAP.get(nome_tabela.lower(), nome_tabela)


class ConnectionBD:
    pg_host = os.environ.get("PG_HOST")
    pg_port = os.environ.get("PG_PORT", "5432")
    pg_db   = os.environ.get("PG_DB")
    pg_user = os.environ.get("PG_USER")
    pg_pass = os.environ.get("PG_PASS")

    def __init__(
        self, variable=None, host=None, port=None, user=None, db=None, pwd=None
    ):
        # Mantém assinatura retrocompatível (variable era usado no MySQL
        # por causa de um bug com o primeiro atributo retornando None).
        self.host = host or ConnectionBD.pg_host
        self.port = port or ConnectionBD.pg_port
        self.user = user or ConnectionBD.pg_user
        self.db   = db   or ConnectionBD.pg_db
        self.pwd  = pwd  or ConnectionBD.pg_pass
        self.variable = variable
        self.cnx = None
        self.cursor = None

    def conectar(self):
        if not self.host or not self.user:
            raise ConnectionError(
                f"Credenciais do banco de dados PostgreSQL nao encontradas. "
                f"Verifique se o arquivo .env existe em: {_ENV_PATH} "
                f"e contém PG_HOST, PG_USER, PG_DB, PG_PASS."
            )
        self.cnx = psycopg2.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.pwd,
            dbname=self.db,
        )
        self.cursor = self.cnx.cursor()

    def desconectar(self):
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
        if self.cnx:
            try:
                self.cnx.close()
            except Exception:
                pass

    def executar_DML(self, comando_dml, valores_dml=None):
        self.conectar()
        self.cursor.execute(comando_dml, valores_dml)
        self.cnx.commit()
        self.desconectar()

    def executar_DQL(self, comando_dql, valores_dql=None):
        self.conectar()
        self.cursor.execute(comando_dql, valores_dql)
        resposta = self.cursor.fetchall()
        self.desconectar()
        return resposta


class BancoDados(ConnectionBD):
    def __init__(self, nome_tabela, name_col=None, parent=None):
        super().__init__(parent)
        self.nome_tabela_logico = nome_tabela
        self.nome_tabela = _resolve_table(nome_tabela)
        self.name_col = name_col

    # ── Alertas ────────────────────────────────────────────────

    def incluir(
        self,
        chassi,
        cliente,
        alerta,
        data,
        hora_dtc,
        hora_envio,
        latitude,
        longitude,
        enviado_para,
        id_mensagem,
        horimetro,
        data_envio,
        # Novos campos (migração PG / opc_notifications_events)
        notification_id=None,
        color_id=None,
        severity=None,
        three_letter_acronym=None,
        machine_model=None,
    ):
        """Insere alerta na tabela rts_alertas.

        O campo ID (serial/autoincrement) é gerado pelo PG — não
        enviamos 0 como no MySQL.
        """
        sql = """
            INSERT INTO {table} (
                chassi, cliente, alerta, data_alerta, hora_alerta,
                data_envio, hora_envio, latitude, longitude,
                enviado_para, id_mensagem, horimetro,
                notification_id, color_id, severity,
                three_letter_acronym, machine_model
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s
            )
        """.format(table=self.nome_tabela)

        values_sql = (
            chassi,
            cliente,
            alerta,
            data,
            hora_dtc,
            data_envio,
            hora_envio,
            latitude,
            longitude,
            enviado_para,
            id_mensagem,
            horimetro,
            notification_id,
            color_id,
            severity,
            three_letter_acronym,
            machine_model,
        )

        c = ConnectionBD()
        c.executar_DML(sql, values_sql)

    def consultar(self, parametro_pesquisa, coluna, dado, coluna2, dado2):
        """Consulta dedup de alertas. Retorna último registro por DATA_ENVIO.

        NOTA: coluna/coluna2 são nomes internos conhecidos (Chassi, Alerta)
        — não vêm de input de usuário.
        """
        sql = (
            f"SELECT {parametro_pesquisa} FROM {self.nome_tabela}"
            f" WHERE {coluna} = %s AND {coluna2} = %s"
            f" ORDER BY data_envio DESC LIMIT 1"
        )
        c = ConnectionBD()
        res = c.executar_DQL(sql, (dado, dado2))
        return res

    def consultar_hoje(self, chassi: str, alerta: str) -> bool:
        """Retorna True se (chassi, alerta) já foi enviado hoje (dia calendário).

        Usa comparação no lado do banco via CURRENT_DATE para evitar problemas
        de tipo entre datetime.date e datetime.datetime no psycopg2 quando a
        coluna data_envio é TIMESTAMP ao invés de DATE.
        O cast ::date garante compatibilidade com ambos os tipos de coluna.
        """
        sql = (
            f"SELECT 1 FROM {self.nome_tabela}"
            f" WHERE chassi = %s AND alerta = %s"
            f" AND data_envio::date = CURRENT_DATE"
            f" LIMIT 1"
        )
        c = ConnectionBD()
        res = c.executar_DQL(sql, (chassi, alerta))
        return len(res) > 0

    # ── Clientes (contatos) ────────────────────────────────────

    def incluir_cliente(
        self, uf, cliente, responsavel, telefone, email, cen, idCliente
    ):
        """Insere cliente na tabela rts_contatos.

        O campo identificador (serial PK) é gerado pelo PG.
        """
        sql = f"""
            INSERT INTO {self.nome_tabela} (
                uf, cliente, jdlink_id,
                responsavel, telefone, email, cen
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values_sql = (uf, cliente, idCliente, responsavel, telefone, email, cen)
        c = ConnectionBD()
        c.executar_DML(sql, values_sql)

    def consultar_cliente(self, cliente: str, id_org: str, telefone: str):
        """Busca clientes com ILIKE (case-insensitive).

        Agora usa queries parametrizadas — corrige a vulnerabilidade
        de SQL injection que existia com f-strings no MySQL.
        """
        conditions = []
        params = []

        if cliente:
            conditions.append('cliente ILIKE %s')
            params.append(f"%{cliente}%")
        if id_org:
            conditions.append('jdlink_id ILIKE %s')
            params.append(f"%{id_org}%")
        if telefone:
            conditions.append('telefone ILIKE %s')
            params.append(f"%{telefone}%")

        if not conditions:
            return []

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM {self.nome_tabela} WHERE {where}"

        c = ConnectionBD()
        try:
            results = c.executar_DQL(sql, tuple(params))
        except Exception as e:
            raise Exception(f"Nao foi possivel consultar o cliente: {e}")

        return results

    def atualizar_cliente(self, **kwargs):
        """Atualiza cliente — agora com query parametrizada."""
        sql = f"""
            UPDATE {self.nome_tabela}
            SET uf = %s,
                cliente = %s,
                jdlink_id = %s,
                responsavel = %s,
                telefone = %s,
                email = %s,
                cen = %s
            WHERE identificador = %s
        """
        params = (
            kwargs["uf"],
            kwargs["cliente"],
            kwargs["id_org"],
            kwargs["responsavel"],
            kwargs["telefone"],
            kwargs["email"],
            kwargs["cen"],
            kwargs["identificador"],
        )

        c = ConnectionBD()
        try:
            c.executar_DML(sql, params)
        except Exception as e:
            raise Exception(f"Nao foi possivel atualizar as informacoes: {e}")

    def excluir_cliente(self, identificador: str):
        """Remove cliente por identificador."""
        sql = f'DELETE FROM {self.nome_tabela} WHERE identificador = %s'
        c = ConnectionBD()
        try:
            c.executar_DML(sql, (identificador,))
        except Exception as e:
            raise Exception(f"Nao foi possivel excluir o cliente: {e}")

    def capture_columns(self):
        """Retorna lista com nomes das colunas da tabela.

        Equivalente PG do SHOW COLUMNS do MySQL.
        """
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
        """
        c = ConnectionBD()
        try:
            results = c.executar_DQL(sql, (self.nome_tabela,))
            return [row[0] for row in results]
        except Exception:
            raise

    # ── Utilitários ────────────────────────────────────────────

    def criar_tabela(self, colunas):
        """CREATE TABLE IF NOT EXISTS — raramente usado, mas preservado."""
        sql = f"CREATE TABLE IF NOT EXISTS {self.nome_tabela} ({colunas})"
        c = ConnectionBD()
        try:
            c.executar_DML(sql)
        except Exception:
            pass

    def excluir_tabela(self):
        sql = f"DROP TABLE IF EXISTS {self.nome_tabela}"
        c = ConnectionBD()
        try:
            c.executar_DML(sql)
        except Exception:
            print("Tabela nao existe ou nao foi possivel limpar a tabela")

    def dt_tabela(self):
        """Retorna a data de criação da tabela.

        PostgreSQL não tem CREATE_TIME em information_schema.tables.
        Usamos pg_stat_user_tables ou, como fallback, a data atual.
        Essa função é usada só pelo export_alerts.py para nomear
        o arquivo Excel exportado.
        """
        sql = """
            SELECT COALESCE(
                (SELECT create_date FROM pg_stat_user_tables
                 WHERE schemaname = 'public' AND relname = %s),
                CURRENT_DATE
            )
        """
        # pg_stat_user_tables não tem create_date confiável.
        # Alternativa pragmática: pegar o MIN(data_envio) da tabela,
        # que era o uso real no export_alerts (data do primeiro registro).
        sql_fallback = f"""
            SELECT COALESCE(
                MIN(data_envio),
                CURRENT_DATE
            ) FROM {self.nome_tabela}
        """
        c = ConnectionBD()
        try:
            result = c.executar_DQL(sql_fallback)
            if result and result[0][0]:
                val = result[0][0]
                # Se vier como datetime, pega só date
                if hasattr(val, 'date'):
                    return val.date()
                return val
        except Exception:
            pass
        from datetime import date as _date
        return _date.today()


if __name__ == "__main__":
    bd = BancoDados(nome_tabela="contatos")
    colunas = bd.capture_columns()
    print(colunas)
