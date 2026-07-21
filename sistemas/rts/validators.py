"""
VALIDATORS — Módulo centralizado de validação
Reduz duplicação de código entre main.py e batch_alert_sender.py
"""

import logging

logger = logging.getLogger(__name__)


def validate_and_normalize_phone(phone_str: str) -> tuple[str | None, bool]:
    """
    Valida e normaliza número de telefone.

    Aceita:
    - Formato nacional (11 dígitos): 11998765432 → 5511998765432
    - Formato internacional (13 dígitos): 5511998765432 → 5511998765432

    Valida DDD (não pode começar com 0 ou 1 no 1º ou 3º dígito conforme formato).

    Args:
        phone_str: String com número de telefone

    Returns:
        tuple: (telefone_normalizado, is_valid)
               - se inválido: (telefone_sujo, False)
               - se válido: (telefone_internacional, True)
    """

    if not phone_str:
        return None, False

    # Limpar string
    phone_clean = str(phone_str).strip()
    phone_clean = phone_clean.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Validar se contém apenas dígitos
    if not phone_clean or not phone_clean.isdigit():
        return phone_clean, False

    # Aceitar 11 dígitos (nacional) ou 13 dígitos (internacional com 55)
    if len(phone_clean) == 11:
        # Formato nacional: 11 dígitos
        # DDD válido no Brasil: 11-99 (primeiro dígito de 1-9, segundo dígito de 1-9)
        # Rejeita apenas se começar com 0 (que é inválido)
        if phone_clean[0] != '0':
            phone_clean = "55" + phone_clean  # Normaliza para formato internacional
            return phone_clean, True

    elif len(phone_clean) == 13 and phone_clean.startswith("55"):
        # Formato internacional: 55 + DDD + número
        # DDD é o 3º e 4º dígitos (índices 2-3), ambos devem ser de 1-9 (não 0)
        # phone_clean[2] é o primeiro dígito do DDD
        if phone_clean[2] != '0':
            return phone_clean, True

    # Se chegou aqui, é inválido
    return phone_clean, False


# Aliases para compatibilidade com código existente
def validate_phone(phone_str: str) -> bool:
    """Retorna apenas o status de validação (compatível com código anterior)"""
    _, is_valid = validate_and_normalize_phone(phone_str)
    return is_valid


def normalize_phone(phone_str: str) -> str | None:
    """Retorna apenas o telefone normalizado (compatível com código anterior)"""
    phone_normalized, _ = validate_and_normalize_phone(phone_str)
    return phone_normalized
