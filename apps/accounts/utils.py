import re


def normalize_argentine_phone(phone):
    """
    Normaliza un teléfono argentino a formato internacional WhatsApp.
    Acepta múltiples formatos de entrada y devuelve "549XXXXXXXXXX" (sin +).

    Ejemplos:
      "+54 9 11 2345-6789"  → "5491123456789"
      "011 15-2345-6789"    → "5491123456789"
      "0341 15-2345678"     → "5493412345678"
      "5491123456789"       → "5491123456789"
    Devuelve None si el número es inválido.
    """
    if not phone:
        return None

    # Limpiamos todo lo que no sea dígito
    digits = re.sub(r'\D', '', str(phone))

    if not digits:
        return None

    # --- Caso 1: ya viene en formato internacional (empieza con 54) ---
    if digits.startswith('54'):
        rest = digits[2:]
        # 54 9 XXXXXXXXXX (13 dígitos total) → móvil completo
        if len(digits) == 13 and rest.startswith('9'):
            return digits
        # 54 XXXXXXXXXX (12 dígitos) → asumimos móvil, agregamos el 9
        if len(digits) == 12:
            return f'549{rest}'
        # 54 9 XXX XXXX XXXX
        if len(digits) >= 13:
            return digits

    # --- Caso 2: formato local con 0 inicial ---
    if digits.startswith('0'):
        # Quitamos el 0
        without_zero = digits[1:]

        # Buenos Aires: 011 ...
        if without_zero.startswith('11'):
            rest = without_zero[2:]
            # Si empieza con 15 es móvil: 011 15 XXXX-XXXX
            if rest.startswith('15'):
                return f'54911{rest[2:]}'
            # Si no, es fijo o ya sin 15: 011 XXXX-XXXX
            return f'54911{rest}'

        # Otras áreas: 0[área]15[número]
        match = re.match(r'^(\d{2,4})15(\d+)$', without_zero)
        if match:
            area, number = match.groups()
            return f'549{area}{number}'

        # Sin 15: fijo o ya normalizado
        return f'54{without_zero}'

    # --- Caso 3: sin 0 inicial (ej: "11 2345-6789") ---
    # Buenos Aires sin 0
    if digits.startswith('11'):
        rest = digits[2:]
        if rest.startswith('15'):
            return f'54911{rest[2:]}'
        return f'54911{rest}'

    # Otras áreas: [área]15[número]
    match = re.match(r'^(\d{2,4})15(\d+)$', digits)
    if match:
        area, number = match.groups()
        return f'549{area}{number}'

    # Número de 10 dígitos sin formato: asumimos área de 3 + número de 7
    if len(digits) == 10:
        return f'549{digits}'

    # Fallback: si tiene 13 dígitos, asumimos que ya está listo
    if len(digits) == 13:
        return digits

    return None


def format_phone_display(phone):
    """Devuelve un teléfono formateado para mostrar al usuario."""
    if not phone:
        return ''
    if phone.startswith('54911') and len(phone) >= 13:
        return f'+54 9 11 {phone[5:9]}-{phone[9:]}'
    if phone.startswith('549') and len(phone) >= 12:
        return f'+54 9 {phone[3:]}'
    return f'+{phone}'