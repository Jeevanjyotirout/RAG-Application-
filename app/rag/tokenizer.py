def count_tokens(text: str) -> int:
    """
    Stima il numero di token in un testo usando la regola "un token ~ 4 caratteri".
    Questo è un metodo 'dummy' che non richiede dipendenze esterne.
    """
    if not text:
        return 0
    return round(len(text) / 4)
