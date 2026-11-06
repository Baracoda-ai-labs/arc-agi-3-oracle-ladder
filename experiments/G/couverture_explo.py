"""[G] CW-444 C4 : COUVERTURE de l'exploration générique de P1 contre le HASARD, mode « seul » (exploration seule depuis
RESET, sans les phases v4 : isole l'explorateur), même budget de coups par niveau, même graine, mêmes candidats
(`Explorateur.candidats` : clavier + clics sur objets). Trois bras :
  generique        : `agent_p1.generique.Explorateur` (copie de travail de C, `experiments/films_p1/paquet`), drapeau éteint ;
  generique_films  : le même avec `CHRYS_FILMS_P1=1` (films nets, CCM-318-C) ;
  hasard           : même classe, mais `choisir` = coup tiré au hasard parmi les candidats.
Mesures par niveau joué : victoire, coups, états distincts visités (`len(aretes)`, clé = image masquée).
Usage : couverture_explo.py <dossier_jeux> <sortie_dir> <bras> [budget=150] [graine=0] [jeux…]"""
import json
import os
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
P = R / "experiments/films_p1/paquet"
for p in (P, P / "livraison_p1/code", P / "references/astra4/livraison_astra4/ajouts", P / "livraison_explo/code"):
    sys.path.insert(0, str(p))
TEMOINS = {"vc33", "tu93", "wa30", "s5i5", "cn04"}


def main():
    dossier, sortie, bras = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    budget = int(sys.argv[4]) if len(sys.argv) > 4 else 150
    graine = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    jeux = sys.argv[6:] or sorted(p.name for p in Path(dossier).iterdir() if not p.name.startswith("."))
    assert not TEMOINS & set(jeux), "témoin"
    if bras == "generique_films":
        os.environ["CHRYS_FILMS_P1"] = "1"
    else:
        os.environ.pop("CHRYS_FILMS_P1", None)
    if os.environ.get("CHRYS_G_NOUV") == "1":  # même variante que banc_c4.py, posée avant l'import du runner
        import agent_p1.generique as GEN2
        _prio2 = GEN2.Explorateur.priorite

        def priorite2(self, a, im):
            p = _prio2(self, a, im)
            k = self.cle(im)
            return p - 50.0 if a in self.supposees.get(k, {}) and a not in self.aretes.get(k, {}) else p
        GEN2.Explorateur.priorite = priorite2
    import runner
    from agent_p1.generique import Explorateur

    class Hasard(Explorateur):
        def choisir(self):
            return self.rng.choice(self.candidats(self.lab.image) or [1]), "hasard"
    Ex = Hasard if bras == "hasard" else Explorateur
    import shutil
    for jeu in jeux:
        memoire = sortie / f"memoire_{jeu}"  # repart de memoire_depart pour chaque jeu (comparaison appariée)
        memoire.mkdir(parents=True, exist_ok=True)
        for f in (P / "livraison_p1/memoire_depart").glob("*.json"):
            if not (memoire / f.name).exists():
                shutil.copy(f, memoire / f.name)
        try:
            res = runner.jouer_seul(dossier, jeu, str(sortie), Ex, budget, str(memoire), max_niveaux=20, graine=graine)
        except Exception as e:  # noqa: BLE001 — échec compté
            res = [{"jeu": jeu, "niveau": 1, "victoire": False, "erreur": f"{type(e).__name__}: {e}"[:200]}]
        for ligne in res:
            print("LIGNE", json.dumps({"bras": bras, **{k: ligne.get(k) for k in ("jeu", "niveau", "victoire", "coups")},
                                       "etats": (ligne.get("infos") or {}).get("etats"), "erreur": ligne.get("erreur")}),
                  flush=True)


if __name__ == "__main__":
    main()
