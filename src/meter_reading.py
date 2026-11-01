"""
Regras de decisão sobre a leitura prevista pelo reconhecedor.

Este módulo não depende do PyTorch: recebe a leitura e a confiança já
calculadas e decide o status de cada foto.
"""

# Status possíveis de cada foto após a etapa de leitura.
STATUS_LIDO = "lido"                        # confiança alta, pode ser aceita automaticamente
STATUS_LEITURA_SUSPEITA = "leitura_suspeita"  # confiança baixa, vai para conferência humana
STATUS_SEM_LEITURA = "sem_leitura"          # display não detectado na foto


def reading_status(reading: str, confidence: float, accept_confidence: float) -> str:
    if not reading:
        return STATUS_SEM_LEITURA
    return STATUS_LIDO if confidence >= accept_confidence else STATUS_LEITURA_SUSPEITA


def same_reading(predicted: str, expected) -> bool:
    """Compara leituras como inteiros, ignorando zeros à esquerda do display."""
    try:
        return int(predicted) == int(expected)
    except (TypeError, ValueError):
        return False
