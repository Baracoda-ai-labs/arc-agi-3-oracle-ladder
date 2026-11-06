"""Notation d'une valeur dans une réponse libre (porté du jalon 1, demo_jalon1.py : norm/contient, corrigés et testés)."""
import re
import unicodedata


def norm_valeur(s):
    """Casse, accents, virgule décimale ; on ne colle QUE les espaces intra-nombre (sinon la valeur se colle
    aux chiffres de l'identifiant de source : défaut qui a faussé deux exécutions du jalon 1)."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace(" ", " ").replace(" ", " ").replace(",", ".")
    return re.sub(r"(?<=\d)[ \t](?=\d)", "", s)


def contient(reponse, valeur):
    """Valeur alphanumérique -> sous-chaîne. Nombre pur -> frontière de chiffre des deux côtés."""
    c, v = norm_valeur(reponse), norm_valeur(valeur).strip()
    if re.search(r"[a-z]", v):
        return v in c
    dv = re.sub(r"[^\d.]", "", v)
    return bool(dv) and re.search(rf"(?<![\d.]){re.escape(dv)}(?![\d.])", c) is not None
