"""Table de faits invalidable (porté du jalon 1, /Users/ts/models/demo/store.py, 2026-08-10).

Repris tel quel : clé (entité, relation), lookup EXACT sans embedding ; `promote()` seule interface d'écriture,
qui incrémente l'époque et archive l'ancienne valeur (rien n'est détruit) ; `invalider()` = changement de statut.
Ajouts T0.7 : lecture à une époque passée (`valeur_a`), liens de dérivation (`parents`) avec invalidation en
cascade des descendants, et extraction de repli par entité (toutes les fiches actives de l'entité reconnue).
"""
import json
import re
import unicodedata
from pathlib import Path


def norm(s):
    """Normalisation d'adressage : casse, accents, espaces. Déterministe."""
    s = unicodedata.normalize("NFKD", str(s).strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


class FactStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.data, self._index = {"epoque_globale": 1, "entrees": {}}, None
        if self.path and self.path.exists():
            self.data = json.loads(self.path.read_text())

    @staticmethod
    def key(entite, relation):
        return f"{norm(entite)}||{norm(relation)}"

    def get(self, entite, relation):
        """Entrée ACTIVE, ou None."""
        e = self.data["entrees"].get(self.key(entite, relation))
        return e if e is not None and e["statut"] == "actif" else None

    def valeur_a(self, entite, relation, epoque):
        """Valeur en vigueur à une époque donnée (graphe temporel) : l'historique n'est jamais perdu."""
        e = self.data["entrees"].get(self.key(entite, relation))
        if e is None:
            return None
        versions = [*e["historique"], {"epoque": e["epoque"], "valeur": e["valeur"]}]
        ok = [v for v in versions if v["epoque"] <= epoque]
        return ok[-1]["valeur"] if ok else None

    # ---------- écriture ----------
    def promote(self, entite, relation, valeur, provenance, alias_entite=None, mots_relation=None, parents=()):
        """Crée l'entrée, ou incrémente son époque en archivant l'ancienne valeur. Ne remplace jamais."""
        k = self.key(entite, relation)
        e = self.data["entrees"].get(k)
        if e is None:
            self.data["entrees"][k] = {
                "entite": entite, "relation": relation, "valeur": valeur, "epoque": 1, "provenance": provenance,
                "statut": "actif", "alias_entite": alias_entite or [entite], "mots_relation": mots_relation or [relation],
                "parents": [self.key(*p) for p in parents], "historique": []}
            self._index = None
            return 1
        e["historique"].append({"epoque": e["epoque"], "valeur": e["valeur"], "provenance": e["provenance"],
                                "statut": "perime"})
        e["epoque"] += 1
        e["valeur"], e["provenance"], e["statut"] = valeur, provenance, "actif"
        self.data["epoque_globale"] = max(self.data["epoque_globale"], e["epoque"])
        return e["epoque"]

    def descendants(self, entite, relation):
        """Clés dérivées (transitivement) de ce fait."""
        out, front = [], [self.key(entite, relation)]
        while front:
            k = front.pop()
            for k2, e in self.data["entrees"].items():
                if k in e.get("parents", []) and k2 not in out:
                    out.append(k2)
                    front.append(k2)
        return out

    def invalider(self, entite, relation, cascade=True):
        """Périme une entrée sans la détruire ; ses descendants passent « a_reverifier ». Renvoie les clés touchées."""
        e = self.data["entrees"].get(self.key(entite, relation))
        if not e:
            return []
        e["statut"] = "perime"
        touched = [self.key(entite, relation)]
        if cascade:
            for k in self.descendants(entite, relation):
                self.data["entrees"][k]["statut"] = "a_reverifier"
                touched.append(k)
        return touched

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))

    # ---------- extraction déterministe ----------
    def _surface(self):
        if self._index is None:
            self._index = {}
            for k, e in self.data["entrees"].items():
                for al in e.get("alias_entite", [e["entite"]]):
                    self._index.setdefault(norm(al), []).append(k)
        return self._index

    def extraire(self, question):
        """Jalon 1 : forme de surface la plus spécifique d'abord ; entrée dont TOUS les mots de relation figurent."""
        q = norm(question)
        idx = self._surface()
        for surf in sorted((s for s in idx if s in q), key=len, reverse=True):
            for k in idx[surf]:
                e = self.data["entrees"][k]
                if e["statut"] == "actif" and all(norm(m) in q for m in e.get("mots_relation", [])):
                    return e
        return None

    def extraire_entite(self, question):
        """Repli : si une entité est reconnue sans relation exacte, toutes ses fiches actives."""
        q = norm(question)
        idx = self._surface()
        for surf in sorted((s for s in idx if s in q), key=len, reverse=True):
            es = [self.data["entrees"][k] for k in idx[surf] if self.data["entrees"][k]["statut"] == "actif"]
            if es:
                return es
        return []
