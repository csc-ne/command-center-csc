#!/usr/bin/env python3
"""
BATCH ALERT SENDER — Integração com RTS

Módulo baseado em send_unsent_alerts.py
Envia automaticamente alertas não-enviados do BD
Integrado ao loop principal do RTS

Função: send_pending_alerts()
Chamada a cada intervalo configurável (default: 60s)
"""

import logging
import re
from datetime import datetime
from BD_alertas import BancoDados
from whatsapp_api import send_wpp
from validators import validate_and_normalize_phone

# Logger
logger = logging.getLogger(__name__)

class BatchAlertSender:
    """
    Envia em lote alertas não-enviados do BD
    Funcionalidade idêntica a send_unsent_alerts.py
    """

    def __init__(self):
        self.total = 0
        self.sucesso = 0
        self.falha = 0
        self.last_run = None

    def get_unsent_alerts(self):
        """Busca alertas não-enviados do BD"""
        try:
            bd = BancoDados(nome_tabela="Alertas")
            bd.conectar()

            # Mesma query do script send_unsent_alerts.py
            query = """
                SELECT
                    ID, CHASSI, CLIENTE, ALERTA,
                    DATA_ALERTA, HORA_ALERTA,
                    HORIMETRO
                FROM rts_alertas
                WHERE ENVIADO_PARA IS NULL
                   OR ENVIADO_PARA = 'WPP_NAO_ENVIADO'
                   OR ENVIADO_PARA = ''
                ORDER BY DATA_ALERTA DESC, HORA_ALERTA DESC
                LIMIT 100
            """

            bd.cursor.execute(query)
            alertas = bd.cursor.fetchall()
            bd.desconectar()

            return alertas

        except Exception as e:
            logger.error(f"[BatchSender] Erro ao buscar alertas: {e}")
            return []

    def get_phone_for_client(self, cliente_id, nome_cliente=None):
        """
        Busca telefone do cliente no BD usando JDLink_ID (consistente com main.py).

        Args:
            cliente_id: JDLink_ID (ID numérico do cliente) — chave primária confiável
            nome_cliente: Nome do cliente (usado apenas para logs)

        Returns:
            Telefone do cliente ou None se não encontrado
        """
        try:
            bd = BancoDados(nome_tabela="contatos")
            bd.conectar()

            # SINCRONIZADO COM main.py: usa JDLink_ID como chave primária (mais confiável que nome)
            query = 'SELECT telefone FROM rts_contatos WHERE jdlink_id = %s LIMIT 1'
            bd.cursor.execute(query, (cliente_id,))
            result = bd.cursor.fetchone()

            bd.desconectar()

            if result and result[0]:
                return str(result[0]).strip()
            return None

        except Exception as e:
            logger.error(f"[BatchSender] Erro ao buscar telefone para {nome_cliente or cliente_id}: {e}")
            return None

    def update_alert_sent(self, id_alerta, wa_id, msg_id):
        """Atualiza alerta como enviado no BD"""
        try:
            bd = BancoDados(nome_tabela="Alertas")
            bd.conectar()

            query = """
                UPDATE rts_alertas
                SET ENVIADO_PARA = %s, ID_MENSAGEM = %s
                WHERE ID = %s
            """

            bd.cursor.execute(query, (wa_id, msg_id, id_alerta))
            bd.cnx.commit()
            bd.desconectar()

            return True

        except Exception as e:
            logger.error(f"[BatchSender] Erro ao atualizar alerta {id_alerta}: {e}")
            return False


    def send_batch(self, max_alerts=100):
        """
        Envia alertas não-enviados em lote
        Retorna: (total, sucesso, falha)
        """

        logger.info(f"[BatchSender] Iniciando envio de alertas não-enviados...")

        # Buscar alertas
        alertas = self.get_unsent_alerts()

        if not alertas:
            logger.info(f"[BatchSender] Nenhum alerta para enviar")
            self.last_run = datetime.now()
            return 0, 0, 0

        self.total = len(alertas)
        self.sucesso = 0
        self.falha = 0

        logger.info(f"[BatchSender] Encontrados {self.total} alerta(s)")

        # Processar cada alerta
        for id_alerta, chassi, cliente, alerta, data_alerta, hora_alerta, horimetro in alertas[:max_alerts]:

            # Buscar JDLink_ID do cliente e depois seu telefone
            # NOTA: A query anterior retorna apenas ID, CHASSI, CLIENTE, etc.
            # Precisamos buscar o JDLink_ID a partir do nome do cliente
            try:
                bd_temp = BancoDados(nome_tabela="contatos")
                bd_temp.conectar()
                query_cliente_id = 'SELECT jdlink_id FROM rts_contatos WHERE cliente = %s LIMIT 1'
                bd_temp.cursor.execute(query_cliente_id, (cliente,))
                result_id = bd_temp.cursor.fetchone()
                bd_temp.desconectar()

                if not result_id:
                    logger.warning(f"[BatchSender] {cliente} — Cliente não encontrado na tabela contatos")
                    self.falha += 1
                    continue

                cliente_jdlink_id = result_id[0]
            except Exception as e:
                logger.error(f"[BatchSender] {cliente} — Erro ao buscar JDLink_ID: {e}")
                self.falha += 1
                continue

            # Buscar telefone usando JDLink_ID (sincronizado com main.py)
            telefone = self.get_phone_for_client(cliente_jdlink_id, cliente)

            if not telefone:
                logger.warning(f"[BatchSender] {cliente} — Telefone não encontrado")
                self.falha += 1
                continue

            # Validar e normalizar telefone (usando validador centralizado)
            telefone_normalizado, is_valid = validate_and_normalize_phone(telefone)

            if not is_valid:
                logger.warning(f"[BatchSender] {cliente} — Telefone inválido: {telefone_normalizado}")
                self.falha += 1
                continue

            # Formatar data
            try:
                data_obj = datetime.strptime(str(data_alerta), "%Y-%m-%d")
                data_formatada = data_obj.strftime("%d/%m/%Y")
            except:
                data_formatada = str(data_alerta)

            # Formatar horimetro
            try:
                horo = float(horimetro) if horimetro else 0
            except:
                horo = 0

            # ── Sanitização dos parâmetros de template ──
            # Meta API rejeita NULL, string vazia, \n, \t e 4+ espaços consecutivos.
            # main.py sanitiza via alerts_api; aqui o dado vem cru do BD.
            def _sanitize_param(val, fallback="N/A"):
                if not val:
                    return fallback
                s = str(val).strip()
                s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
                s = re.sub(r" {4,}", "   ", s)   # máx 3 espaços consecutivos
                return s or fallback

            cliente_clean = _sanitize_param(cliente, "CLIENTE_DESCONHECIDO")
            alerta_clean = _sanitize_param(alerta, "ALERTA_SEM_DESCRICAO")
            chassi_clean = _sanitize_param(chassi, "N/A")

            # Enviar alerta
            try:
                logger.info(f"[BatchSender] {cliente_clean} ({chassi_clean[:10]}...) → Enviando...")

                resultado = send_wpp(
                    tel=telefone_normalizado,
                    cliente=cliente_clean,
                    chassi=chassi_clean,
                    data_ocorrencia=data_formatada,
                    horimetro=f"{int(horo)}",
                    notificacao=alerta_clean
                )

                # Validar resultado
                if "error" in resultado:
                    erro = resultado.get("error", {})
                    msg_erro = f"[{erro.get('code')}] {erro.get('message')}"
                    logger.error(f"[BatchSender] {cliente} — Meta API Error: {msg_erro}")
                    self.falha += 1
                    continue

                if "messages" not in resultado or not resultado["messages"]:
                    logger.error(f"[BatchSender] {cliente} — Resposta sem message ID")
                    self.falha += 1
                    continue

                # Extrair IDs
                wa_id = telefone_normalizado
                msg_id = resultado["messages"][0]["id"]

                # Atualizar BD
                if not self.update_alert_sent(id_alerta, wa_id, msg_id):
                    logger.warning(f"[BatchSender] {cliente} — Enviado mas BD não atualizado")
                    self.falha += 1
                    continue

                logger.info(f"[BatchSender] {cliente} ✅ Sucesso (msg_id: {msg_id[:20]}...)")
                self.sucesso += 1

            except Exception as e:
                logger.error(f"[BatchSender] {cliente} — Exception: {e}")
                self.falha += 1
                continue

        # Log final
        logger.info(f"[BatchSender] RELATÓRIO: Total={self.total}, Sucesso={self.sucesso}, Falha={self.falha}")
        if self.total > 0:
            taxa = (self.sucesso / self.total) * 100
            logger.info(f"[BatchSender] Taxa de sucesso: {taxa:.1f}%")

        self.last_run = datetime.now()
        return self.total, self.sucesso, self.falha


# Instância global
_batch_sender = BatchAlertSender()

def send_pending_alerts():
    """
    Função para chamar no loop principal do RTS

    Uso em main.py:
        from batch_alert_sender import send_pending_alerts

        # No loop principal a cada intervalo (ex: 60s):
        send_pending_alerts()

    GATE DE ENVIO:
    Antes de despachar, consulta `runtime_config.should_send_wpp()` que
    combina `wpp_mode` (UI -> tabela runtime_config) com a janela de
    horário comercial. Se o operador colocou em FORCE_OFF, ou está fora
    do expediente em modo AUTO, retornamos (0,0,0) sem tocar no WPP.

    Import lazy: mantém o módulo carregável mesmo se runtime_config
    quebrar (fallback: comportamento legado, envia direto). Importante
    para não regredir o BatchSender em caso de erro novo no gate.
    """
    try:
        from runtime_config import should_send_wpp, get_wpp_mode
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"[BatchSender] runtime_config indisponivel ({e}); "
            f"seguindo com envio direto (comportamento legado)"
        )
        return _batch_sender.send_batch(max_alerts=100)

    if not should_send_wpp():
        mode = get_wpp_mode()
        logger.info(
            f"[BatchSender] Envio bloqueado por gate (wpp_mode={mode}, "
            f"fora do expediente ou pausado manualmente)"
        )
        # Mantem last_run pra UI saber que rodamos a checagem
        _batch_sender.last_run = datetime.now()
        return 0, 0, 0

    return _batch_sender.send_batch(max_alerts=100)


def get_sender_status():
    """Retorna status do ultimo envio"""
    return {
        "total": _batch_sender.total,
        "sucesso": _batch_sender.sucesso,
        "falha": _batch_sender.falha,
        "last_run": _batch_sender.last_run,
    }


if __name__ == "__main__":
    # Teste independente
    sender = BatchAlertSender()
    total, sucesso, falha = sender.send_batch()
    print(f"\nResultado: {total} total, {sucesso} sucesso, {falha} falha")
