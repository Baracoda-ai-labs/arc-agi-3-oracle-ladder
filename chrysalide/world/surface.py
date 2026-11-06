"""Surface procédurale, sans LLM : noms par syllabes (filtrés contre des noms réels) et gabarits d'énoncé français."""
import pathlib
import unicodedata

ONSETS = ["b", "d", "f", "g", "k", "l", "m", "n", "p", "r", "s", "t", "v", "z", "br", "dr", "gl", "kr", "pl", "tr", "vr"]
VOWELS = ["a", "e", "i", "o", "u", "ou", "ai", "eu", "an", "on", "in"]
CODAS = ["", "", "", "r", "l", "n", "s", "x", "k"]
SYLLABES = {"personne": (2, 2), "nom": (2, 3), "societe": (2, 3), "lieu": (2, 3), "devise": (2, 2),
            "produit": (2, 3), "fonction": (2, 2), "source": (2, 3), "etape": (2, 2)}
REAL_PATH = pathlib.Path(__file__).resolve().parents[2] / "data" / "names_real.txt"


def norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def load_real(path=REAL_PATH) -> set:
    return {norm(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


class Namer:
    """Noms uniques dans un monde, rejetés s'ils figurent dans la liste de noms réels."""

    def __init__(self, rng, real: set):
        self.rng, self.real, self.used, self.rejected = rng, real, set(), 0

    def _word(self, kind):
        lo, hi = SYLLABES[kind]
        n = self.rng.randint(lo, hi)
        w = "".join(self.rng.choice(ONSETS) + self.rng.choice(VOWELS) for _ in range(n)) + self.rng.choice(CODAS)
        return w

    def make(self, kind: str) -> str:
        while True:
            if kind == "personne":
                parts = [self._word("personne").capitalize(), self._word("nom").capitalize()]
            else:
                parts = [self._word(kind)]
                if kind not in ("devise", "produit", "fonction"):
                    parts[0] = parts[0].capitalize()
            name = " ".join(parts)
            if any(norm(p) in self.real for p in parts) or norm(name) in self.real:
                self.rejected += 1
                continue
            if name not in self.used:
                self.used.add(name)
                return name


FORMAT = {
    "int": 'Réponds par une seule ligne JSON : {"reponse": <nombre entier>}.',
    "str": 'Réponds par une seule ligne JSON : {"reponse": "<nom exact>"}.',
    "code": 'Réponds par une seule ligne JSON : {"reponse": "<code Python complet de la fonction>"}.',
}

# 5 à 7 gabarits de question par structure ; le choix est tiré à graine fixée.
QUESTIONS = {
    "A1_conversion": [
        "Combien de {vers} obtient-on au bureau de change de {lieu} pour {montant} {de} ?",
        "Au bureau de change de {lieu}, on remet {montant} {de}. Combien de {vers} reçoit-on ?",
        "Quelqu'un convertit {montant} {de} en {vers} au bureau de change de {lieu}. Quel montant touche-t-il ?",
        "Quel est le résultat, en {vers}, de la conversion de {montant} {de} au bureau de {lieu} ?",
        "Pour {montant} {de} changés à {lieu}, combien de {vers} sont versés ?",
        "On échange {montant} {de} contre des {vers} au bureau de change de {lieu}. Combien en obtient-on ?",
    ],
    "A2_registre": [
        "Combien de caisses de {produit} l'entrepôt de {lieu} contient-il à la fin du jour {jour} ?",
        "D'après le registre, quel est le stock de {produit} à {lieu} au soir du jour {jour} ?",
        "Au terme du jour {jour}, combien de caisses de {produit} restent dans l'entrepôt de {lieu} ?",
        "Quel stock de caisses de {produit} le registre de {lieu} indique-t-il à la fin du jour {jour} ?",
        "Le jour {jour} au soir, on compte les caisses de {produit} à {lieu}. Combien en trouve-t-on ?",
    ],
    "A3_code": [
        "Écris une fonction Python `{fonction}(x)` qui renvoie le tarif {fonction} de {societe} pour x pièces.",
        "Implémente en Python la fonction `{fonction}(x)` : le tarif appliqué par {societe} à une commande de x pièces.",
        "Donne le code d'une fonction Python `{fonction}(x)` qui calcule le tarif {fonction} de {societe}.",
        "Programme `{fonction}(x)` en Python : elle doit rendre le tarif de {societe} pour une commande de x pièces.",
        "Écris `def {fonction}(x)` en Python, qui applique le tarif {fonction} de {societe} à x pièces.",
    ],
    "B1_fait_date": [
        "Qui dirigeait la société {societe} en {annee} ?",
        "En {annee}, qui était à la tête de {societe} ?",
        "Quelle personne dirigeait {societe} au cours de l'année {annee} ?",
        "Qui assurait la direction de la société {societe} en {annee} ?",
        "En {annee}, à qui revenait la direction de {societe} ?",
        "Nomme la personne qui dirigeait {societe} en {annee}.",
    ],
    "B2_regle_versionnee": [
        "Quel impôt la société {societe} doit-elle pour l'année {annee}, sur un chiffre d'affaires de {montant} ?",
        "En {annee}, {societe} déclare un chiffre d'affaires de {montant}. Quel impôt doit-elle ?",
        "Calcule l'impôt dû par {societe} pour {annee}, son chiffre d'affaires étant de {montant}.",
        "Pour l'année {annee}, combien {societe} paie-t-elle d'impôt sur {montant} de chiffre d'affaires ?",
        "Quel montant d'impôt {societe} verse-t-elle au titre de {annee}, pour un chiffre d'affaires de {montant} ?",
    ],
    "B3_sources": [
        "Où se trouve le siège de la société {societe} ?",
        "Dans quel lieu la société {societe} a-t-elle son siège ?",
        "Selon les règles d'arbitrage, où est établi le siège de {societe} ?",
        "Quel est le lieu du siège de {societe} ?",
        "Après arbitrage des déclarations, où siège la société {societe} ?",
    ],
    "C1_itineraire": [
        "Le jour {jour}, quel est le temps de trajet minimal, en minutes, de {de} à {vers} ?",
        "Combien de minutes faut-il au minimum, le jour {jour}, pour aller de {de} à {vers} ?",
        "Un voyageur part de {de} le jour {jour} pour rejoindre {vers}. Quelle est la durée minimale du trajet en minutes ?",
        "Le jour {jour}, quel est le plus court temps de parcours entre {de} et {vers}, en minutes ?",
        "En minutes, combien dure au mieux le trajet de {de} à {vers} le jour {jour} ?",
    ],
    "C2_ordonnancement": [
        "Quelle est la durée minimale, en jours, du projet {projet} ?",
        "En combien de jours, au minimum, le projet {projet} peut-il être achevé ?",
        "Combien de jours faut-il au moins pour terminer toutes les étapes du projet {projet} ?",
        "Quel est le délai le plus court, en jours, pour mener à bien le projet {projet} ?",
        "Au plus tôt, après combien de jours le projet {projet} est-il terminé ?",
    ],
    "C3_composition": [
        "On part du nombre {x}. On applique {f1}, puis {f2}, puis {f3}. Quel nombre obtient-on ?",
        "Quel est le résultat de {f3}({f2}({f1}({x}))) ?",
        "En partant de {x}, on applique successivement {f1}, {f2} et {f3}. Quel est le résultat ?",
        "Calcule la valeur obtenue quand on applique {f1} à {x}, puis {f2} au résultat, puis {f3}.",
        "Le nombre {x} passe par {f1}, puis par {f2}, puis par {f3}. Que vaut-il à la fin ?",
    ],
}
