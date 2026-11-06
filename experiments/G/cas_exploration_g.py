"""[G] CCM-282-C : trois cas « où expérimenter » tenus à part, vérité MESURÉE dans le vrai jeu (`verite_selection.py`),
choisis par une règle fixée avant toute réponse de Qwen, sur les 36 niveaux publics flèches + clic mesurés :
  ressemblant sélectionnable : un seul sélectionnable, rang 1 du témoin, le moins d'objets → ar25 N2 ;
  ressemblant NON sélectionnable : un seul sélectionnable, rang du témoin ≥ 5 (le plus ressemblant ne répond pas) → cd82 N1 ;
  aucun indice : aucun sélectionnable (piloté présent), même famille que le contrôle positif → ka59 N3.
Sortie au format de `experiments/T3.0/cas_exploration.py` (fusion de `verite.pkl`).
Usage : PYTHONPATH=. .venv/bin/python experiments/G/cas_exploration_g.py"""
import pickle
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(R / "experiments/G"))
from verite_selection import mesurer

SORTIE = R / "experiments/qwen_mac/exploration"
CAS = {"ar25_n2": ("ar25", 2), "cd82_n1": ("cd82", 1), "ka59_n3": ("ka59", 3)}


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    verite = {}
    for nom, (gid, k) in CAS.items():
        ligne, cas = mesurer(gid, k)
        sel = ligne["selectionnables"]
        verite[nom] = sel[0] if len(sel) == 1 else None
        (SORTIE / f"{nom}.pkl").write_bytes(pickle.dumps(cas))
        print(nom, "objets", ligne["objets"], "pilote", ligne["pilote"], "sélectionnables", sel, "témoin", ligne["rang_temoin"],
              "vérité", verite[nom])
    ancienne = pickle.loads((SORTIE / "verite.pkl").read_bytes()) if (SORTIE / "verite.pkl").exists() else {}
    (SORTIE / "verite.pkl").write_bytes(pickle.dumps(ancienne | verite))
    print("verite.pkl", ancienne | verite)


if __name__ == "__main__":
    main()
