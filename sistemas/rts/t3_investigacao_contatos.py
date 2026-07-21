"""
T3 — Investigação: por que só 2/36 alertas do RTA foram enviados pelo RTS?

Execute este script na máquina local com acesso ao PostgreSQL em 192.168.0.106.

Ele cruza os PINs do CSV do RTA com:
1. layer_bronze.opc_notifications_events
   - Para localizar o org_id de cada PIN.
2. public.rts_contatos
   - Para verificar se o org_id está cadastrado na base RTS.

Importante:
Este script identifica se o cliente/PIN está ou não na base rts_contatos.
Ele NÃO comprova envio real pelo RTS, pois isso exigiria cruzamento com logs/tabela de envio.

Uso:
    python t3_investigacao_contatos.py
"""

import csv
import os
import sys
import platform
import psycopg2
from datetime import datetime
from dotenv import load_dotenv

# .env centralizado em C:\env\.env no host Windows.
_ENV_PATH = r"C:\env\.env" if platform.system() == "Windows" else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH)


# ─────────────────────────────────────────────────────────────
# Ajuste de encoding para evitar erro no terminal Windows/cp1252
# ─────────────────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Configurações
# ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILENAME = "RTA_alertas_2026-06-09_2026-06-09.csv"
CSV_PATH = os.path.join(SCRIPT_DIR, CSV_FILENAME)

# Config PG lida do .env central (C:\env\.env). Sem fallbacks — se PG_PASS
# nao estiver setado, o processo falha rapido em vez de tentar senha default.
def _require(name):
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name} (esperada em C:\\env\\.env)")
    return v

PG = dict(
    host=_require("PG_HOST"),
    port=int(os.getenv("PG_PORT", "5432")),
    dbname=_require("PG_DB"),
    user=_require("PG_USER"),
    password=_require("PG_PASS"),
)


# Se o CSV não estiver no mesmo diretório, tenta na pasta uploads
if not os.path.exists(CSV_PATH):
    alt = os.path.join(SCRIPT_DIR, "uploads", CSV_FILENAME)

    if os.path.exists(alt):
        CSV_PATH = alt
    else:
        print(f"[ERRO] CSV não encontrado em: {CSV_PATH}")
        print(f"[ERRO] Também não encontrado em: {alt}")
        print()
        print(f"Coloque o arquivo '{CSV_FILENAME}' na pasta do RTS ou na pasta uploads.")
        sys.exit(1)


def limpar_texto(valor):
    """
    Limpa valores vindos do CSV.
    """
    if valor is None:
        return ""

    return str(valor).strip().strip('"')


def carregar_csv():
    """
    Lê o CSV do RTA e retorna uma lista de alertas.
    """
    csv_rows = []

    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")

        for row in reader:
            csv_rows.append({
                "pin": limpar_texto(row.get("PIN")),
                "cliente_rta": limpar_texto(row.get("Cliente")),
                "cor": limpar_texto(row.get("Cor")),
                "tipo": limpar_texto(row.get("Tipo")),
                "horario": limpar_texto(row.get("Horario")),
                "cidade": limpar_texto(row.get("Cidade")),
                "estado": limpar_texto(row.get("Estado")),
                "regional": limpar_texto(row.get("Regional")),
                "enviado_rts_csv": limpar_texto(row.get("Enviado RTS")),
            })

    return csv_rows


def buscar_pin_org_id(cur, pins):
    """
    Busca o org_id de cada PIN na tabela de eventos.
    """
    cur.execute("""
        SELECT DISTINCT
            serial_number,
            org_id
        FROM layer_bronze.opc_notifications_events
        WHERE serial_number = ANY(%s)
    """, (pins,))

    pin_to_org = {}

    for serial_number, org_id in cur.fetchall():
        if serial_number and org_id is not None:
            pin_to_org[str(serial_number).strip()] = str(org_id).strip()

    return pin_to_org


def buscar_contatos_rts(cur):
    """
    Busca todos os contatos cadastrados no RTS.

    A chave de cruzamento é:
        rts_contatos.jdlink_id = opc_notifications_events.org_id
    """
    cur.execute("""
        SELECT
            cliente,
            jdlink_id
        FROM public.rts_contatos
    """)

    contatos = {}

    for cliente, jdlink_id in cur.fetchall():
        if jdlink_id:
            contatos[str(jdlink_id).strip()] = cliente

    return contatos


def salvar_relatorio(report_path, sep, csv_rows, na_base, fora_base, org_ids_faltantes):
    """
    Salva o relatório em arquivo .txt.
    """
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO T3 — ALERTAS RTA X BASE RTS CONTATOS (09/06/2026)\n")
        f.write(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write(f"{sep}\n\n")

        f.write("RESUMO\n")
        f.write("-" * 80 + "\n")
        f.write(f"Total alertas RTA:                    {len(csv_rows)}\n")
        f.write(f"Alertas com cliente na base RTS:      {len(na_base)}\n")
        f.write(f"Alertas fora da base rts_contatos:    {len(fora_base)}\n")
        f.write("\n")

        f.write("OBSERVAÇÃO IMPORTANTE\n")
        f.write("-" * 80 + "\n")
        f.write(
            "Este relatório identifica se o org_id do alerta existe na tabela "
            "public.rts_contatos.\n"
        )
        f.write(
            "Ou seja, ele valida se o cliente está cadastrado na base RTS.\n"
        )
        f.write(
            "Ele NÃO comprova envio real da mensagem pelo RTS. Para isso, "
            "é necessário cruzar com logs/tabelas de envio.\n"
        )
        f.write("\n")

        f.write("CLIENTES FORA DA BASE RTS, PRECISAM SER CADASTRADOS\n\n")
        f.write(
            f"{'#':<3} "
            f"{'Cliente RTA':<50} "
            f"{'PIN':<25} "
            f"{'org_id':<12} "
            f"{'Regional':<8} "
            f"{'Cidade':<25} "
            f"{'Estado':<15}\n"
        )
        f.write("-" * 150 + "\n")

        for i, r in enumerate(fora_base, 1):
            f.write(
                f"{i:<3} "
                f"{r['cliente_rta'][:49]:<50} "
                f"{r['pin']:<25} "
                f"{r['org_id']:<12} "
                f"{r['regional']:<8} "
                f"{r['cidade'][:24]:<25} "
                f"{r['estado']:<15}\n"
            )

        f.write("\n")
        f.write(f"org_ids faltantes em rts_contatos ({len(org_ids_faltantes)}):\n")

        for oid in sorted(org_ids_faltantes):
            f.write(f"  org_id={oid}\n")

        f.write("\n")
        f.write("CLIENTES JÁ NA BASE RTS\n")
        f.write("-" * 80 + "\n")

        for r in na_base:
            f.write(
                f"  Cliente RTA: {r['cliente_rta']} | "
                f"PIN: {r['pin']} | "
                f"org_id: {r['org_id']} | "
                f"Cliente RTS: {r['cliente_rts']}\n"
            )


def main():
    # 1. Ler CSV
    csv_rows = carregar_csv()

    pins = sorted(set(r["pin"] for r in csv_rows if r["pin"]))

    print(f"CSV: {len(csv_rows)} alertas, {len(pins)} PINs únicos")
    print(f"Arquivo CSV: {CSV_PATH}")
    print()

    if not csv_rows:
        print("[ERRO] O CSV não possui linhas para processar.")
        sys.exit(1)

    if not pins:
        print("[ERRO] Nenhum PIN válido foi encontrado no CSV.")
        sys.exit(1)

    conn = None
    cur = None

    try:
        # 2. Conectar ao PostgreSQL
        conn = psycopg2.connect(**PG)
        cur = conn.cursor()

        # 3. PIN -> org_id via opc_notifications_events
        pin_to_org = buscar_pin_org_id(cur, pins)

        pins_sem_evento = [p for p in pins if p not in pin_to_org]

        print(f"PINs encontrados em opc_notifications_events: {len(pin_to_org)}/{len(pins)}")

        if pins_sem_evento:
            print("PINs NÃO encontrados na tabela de eventos:")
            for pin in pins_sem_evento:
                print(f"  {pin}")

        print()

        # 4. Todos os contatos do RTS
        contatos = buscar_contatos_rts(cur)

        print(f"Total contatos em rts_contatos: {len(contatos)}")
        print()

        # 5. Cruzamento
        na_base = []
        fora_base = []
        org_ids_faltantes = set()

        for item in csv_rows:
            pin = item["pin"]
            org_id = pin_to_org.get(pin)

            in_rts = org_id is not None and org_id in contatos
            cliente_rts = contatos.get(org_id, "-") if org_id else "-"

            record = {
                **item,
                "org_id": org_id or "N/A",
                "na_base_rts": in_rts,
                "cliente_rts": cliente_rts,
            }

            if in_rts:
                na_base.append(record)
            else:
                fora_base.append(record)

                if org_id:
                    org_ids_faltantes.add(org_id)

        # 6. Relatório no terminal
        sep = "=" * 150

        print(sep)
        print("RELATÓRIO T3 — ALERTAS RTA X BASE RTS CONTATOS (09/06/2026)")
        print(sep)
        print()

        print(f"Total alertas RTA:                    {len(csv_rows)}")
        print(f"Alertas com cliente na base RTS:      {len(na_base)}")
        print(f"Alertas fora da base rts_contatos:    {len(fora_base)}")
        print()

        print("OBSERVAÇÃO:")
        print("Este cruzamento valida cadastro em rts_contatos.")
        print("Ele não comprova envio real pelo RTS.")
        print("Para investigar envio real, será necessário cruzar com logs/tabela de envios.")
        print()

        print("CLIENTES FORA DA BASE RTS, PRECISAM SER CADASTRADOS")
        print()

        print(
            f"{'#':<3} "
            f"{'Cliente RTA':<50} "
            f"{'PIN':<25} "
            f"{'org_id':<12} "
            f"{'Regional':<8} "
            f"{'Cidade':<25} "
            f"{'Estado':<15}"
        )
        print("-" * 150)

        for i, r in enumerate(fora_base, 1):
            print(
                f"{i:<3} "
                f"{r['cliente_rta'][:49]:<50} "
                f"{r['pin']:<25} "
                f"{r['org_id']:<12} "
                f"{r['regional']:<8} "
                f"{r['cidade'][:24]:<25} "
                f"{r['estado']:<15}"
            )

        print()
        print(f"org_ids que precisam ser cadastrados em rts_contatos ({len(org_ids_faltantes)}):")

        for oid in sorted(org_ids_faltantes):
            print(f"  org_id={oid}")

        print()
        print("CLIENTES JÁ NA BASE RTS:")
        for r in na_base:
            print(
                f"  {r['cliente_rta']} "
                f"(PIN: {r['pin']}, org_id: {r['org_id']}, RTS: {r['cliente_rts']})"
            )

        # 7. Salvar relatório em arquivo
        report_path = os.path.join(
            SCRIPT_DIR,
            f"T3_relatorio_contatos_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        )

        salvar_relatorio(
            report_path=report_path,
            sep=sep,
            csv_rows=csv_rows,
            na_base=na_base,
            fora_base=fora_base,
            org_ids_faltantes=org_ids_faltantes,
        )

        print()
        print(f"Relatório salvo em: {report_path}")

    except psycopg2.Error as e:
        print("[ERRO] Falha ao acessar o PostgreSQL.")
        print(e)
        sys.exit(1)

    except Exception as e:
        print("[ERRO] Falha inesperada ao executar o script.")
        print(e)
        sys.exit(1)

    finally:
        if cur:
            cur.close()

        if conn:
            conn.close()


if __name__ == "__main__":
    main()