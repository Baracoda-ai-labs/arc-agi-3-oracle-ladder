"""[G] CW-447/448 C4 : banc P1 « moteur seul » (celui de D, `experiments/C2_but/banc.py`, code figé du paquet intact,
variantes par monkeypatch AVANT l'import de l'agent). Variante G : `CHRYS_G_INEFF=1` → dans l'exploration générique, un
coup « clic sur une case » déjà vu SANS effet (image masquée identique) et jamais AVEC effet passe en DERNIER dans l'ordre
de priorité (ordonnancement seulement : il reste jouable). Constat (ft09 N1, `CHRYS_C2=groupes`) : 114 clics sans effet
sur 37 cases seulement, 104 répétitions, aucune case à la fois sans effet et efficace.
Usage : CHRYS_C2=groupes [CHRYS_G_INEFF=1] PYTHONPATH=. .venv/bin/python experiments/G/banc_c4.py <sortie> [jeu …]"""
import os
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "experiments/C2_but"))
import banc

if os.environ.get("CHRYS_G_INEFF") == "1":
    import agent_p1.generique as GEN
    _prio = GEN.Explorateur.priorite

    def _bilan_clics(self):
        if getattr(self, "_n_aretes", -1) != sum(len(v) for v in self.aretes.values()):
            sans, avec = set(), set()
            for k0, d in self.aretes.items():
                for a, k1 in d.items():
                    if isinstance(a, tuple):
                        (avec if k1 not in (k0, "mort") else sans).add(a)
            self._sans, self._avec = sans - avec, avec
            self._n_aretes = sum(len(v) for v in self.aretes.values())
        return self._sans

    def priorite(self, a, im):
        p = _prio(self, a, im)
        return p - 100.0 if isinstance(a, tuple) and a in _bilan_clics(self) else p
    GEN.Explorateur.priorite = priorite

if os.environ.get("CHRYS_G_NOUV") in ("1", "2"):
    # variante 2 (CW-448, navigation) : un coup non essayé dont l'arête inverse supposée ramène à un état DÉJÀ VU passe
    # après les autres coups non essayés (ordonnancement seulement)
    import agent_p1.generique as GEN2
    _prio2 = GEN2.Explorateur.priorite

    def priorite2(self, a, im):
        p = _prio2(self, a, im)
        k = self.cle(im)
        if os.environ.get("CHRYS_G_NOUV") == "2" and "mort" in self.aretes.get(k, {}).values():
            return p  # correctif (CW-449) : pas de nouveauté dans un état d'où une mort a été vue
        return p - 50.0 if a in self.supposees.get(k, {}) and a not in self.aretes.get(k, {}) else p
    GEN2.Explorateur.priorite = priorite2

def main_t4(sortie, noms=()):
    """Même boucle que `banc.main` de D, sur les jeux générés de T4 (aucun témoin)."""
    import json
    import shutil

    import agent_p1.jouer as J
    sortie = Path(sortie)
    src = R / "experiments/T4/jeux/t4/environment_files"
    jeux = sortie / "jeux"
    noms = sorted(noms) or sorted(p.name for p in src.iterdir() if p.is_dir())
    for n in noms:
        if not (jeux / n).exists():
            shutil.copytree(src / n, jeux / n)
    memoire = sortie / "memoire_inter_jeux"
    memoire.mkdir(parents=True, exist_ok=True)
    for f in (banc.P / "livraison_p1/memoire_depart").glob("*.json"):
        if not (memoire / f.name).exists():
            shutil.copy(f, memoire / f.name)
    out = {}
    for g in noms:
        try:
            res = J.jouer_jeu(str(jeux), g, str(sortie), 150, str(memoire), graine=int(os.environ.get("G_GRAINE", "0")))
            out[g] = [x["coups"] if x["victoire"] else None for x in res]
        except Exception as e:  # noqa: BLE001 — échec compté
            out[g] = [f"erreur {type(e).__name__}"]
        (sortie / "banc.json").write_text(json.dumps(out, indent=1))
    print("niveaux", sum(isinstance(c, int) for v in out.values() for c in v),
          "jeux", sum(any(isinstance(c, int) for c in v) for v in out.values()))


if __name__ == "__main__":
    if os.environ.get("G_T4") == "1":
        main_t4(sys.argv[1], sys.argv[2:])
    else:
        banc.main(sys.argv[1], sys.argv[2:])
