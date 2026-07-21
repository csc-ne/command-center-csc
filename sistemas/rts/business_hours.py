# =========== RTS - REAL TIME SUPPORT ============
# JANELA DE EXPEDIENTE
# ================================================
#
# Define a janela de horário comercial que governa:
#   - disparo de alertas via WhatsApp
#   - batch sender (reenvio de alertas pendentes)
#   - contabilização de tempos de atendimento e métricas
#
# Horário atual:
#   - Segunda a Sexta (weekday 0..4)
#   - 08:00 até 17:50 (inclusive)
#
# Regra de negócio:
#   - Fora desse intervalo, o serviço permanece ONLINE (renovação de
#     token WPP/JD continua), mas NÃO dispara alertas nem conta métricas.
#
# Configuração via variáveis de ambiente (opcional):
#   RTS_BUSINESS_START     "HH:MM"       default "08:00"
#   RTS_BUSINESS_END       "HH:MM"       default "17:50"
#   RTS_BUSINESS_DAYS      "0,1,2,3,4"   default "0,1,2,3,4"  (0=seg, 6=dom)

import os
from datetime import datetime, time as dtime


def _parse_time(raw: str, fallback: dtime) -> dtime:
    try:
        h, m = raw.strip().split(":")
        return dtime(int(h), int(m))
    except Exception:
        return fallback


def _parse_days(raw: str) -> set[int]:
    try:
        return {int(d.strip()) for d in raw.split(",") if d.strip() != ""}
    except Exception:
        return {0, 1, 2, 3, 4}


BUSINESS_START = _parse_time(os.environ.get("RTS_BUSINESS_START", "08:00"), dtime(8, 0))
BUSINESS_END = _parse_time(os.environ.get("RTS_BUSINESS_END", "17:50"), dtime(17, 50))
BUSINESS_DAYS = _parse_days(os.environ.get("RTS_BUSINESS_DAYS", "0,1,2,3,4"))


def is_business_hours(now: datetime | None = None) -> bool:
    """
    Retorna True se `now` cai dentro da janela de expediente.
    Se `now` for None, usa datetime.now() (hora local do processo).

    Importante: o container Docker deve rodar com TZ=America/Recife
    para que datetime.now() reflita o horário local correto.
    """
    now = now or datetime.now()
    if now.weekday() not in BUSINESS_DAYS:
        return False
    return BUSINESS_START <= now.time() <= BUSINESS_END


def describe_window() -> str:
    """String amigável para logar na inicialização."""
    days_label = {0: "Seg", 1: "Ter", 2: "Qua", 3: "Qui", 4: "Sex", 5: "Sáb", 6: "Dom"}
    days_str = ",".join(days_label[d] for d in sorted(BUSINESS_DAYS))
    return (
        f"{BUSINESS_START.strftime('%H:%M')}–{BUSINESS_END.strftime('%H:%M')} "
        f"({days_str})"
    )


# ------------------------------------------------------------------
# Teste local rápido:
#   python business_hours.py
# ------------------------------------------------------------------
if __name__ == "__main__":
    now = datetime.now()
    print(f"Agora: {now.isoformat()}  weekday={now.weekday()}")
    print(f"Janela configurada: {describe_window()}")
    print(f"Dentro do expediente? {is_business_hours(now)}")
