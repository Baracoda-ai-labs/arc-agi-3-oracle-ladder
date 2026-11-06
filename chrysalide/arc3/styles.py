# SPDX-License-Identifier: MIT-0
"""D (CW-285, idée de Thomas « personas de joueurs », à la Agent57) : SÉLECTEUR DE STYLES par niveau (CHRYS_STYLES=1).
Un style = des réglages déjà mesurés, lus par le moteur à chaque appel (variables d'environnement) :
- audacieux : plans partiels longs, sans consensus ;
- prudent : consensus des k théories avant le 1er coup d'un plan (CW-251), un seul coup partiel à la fois ;
- explorateur : le moteur se tait, l'explorateur (ou Franzen) joue ;
- reflechi : test actif des buts (C, CW-280), plans partiels courts.
Le sélecteur joue chaque style par TRANCHES de coups ; récompense d'une tranche = images nouvelles du niveau par coup
− ½ · divergences par coup (un plan démenti) ; il prend d'abord chaque style une fois (ordre ci-dessus), puis UCB1 ;
il coupe une tranche dès que le style stagne (aucune image nouvelle sur la moitié de la tranche). Remis à zéro à chaque
niveau. Aucun LLM, aucune connaissance du jeu."""
import hashlib
import math
import os

import numpy as np

STYLES = {
    "audacieux": {"CHRYS_CONSENSUS": "0", "CHRYS_PARTIEL_COUPS": "10", "CHRYS_TEST_BUTS": "0"},
    "prudent": {"CHRYS_CONSENSUS": "1", "CHRYS_PARTIEL_COUPS": "1", "CHRYS_TEST_BUTS": "0"},
    "explorateur": None,
    "reflechi": {"CHRYS_CONSENSUS": "0", "CHRYS_PARTIEL_COUPS": "3", "CHRYS_TEST_BUTS": "1"},
}


def actif():
    return os.environ.get("CHRYS_STYLES") == "1"


class Selecteur:
    def __init__(self, tranche=None, styles=None, c=None):
        self.tranche = int(tranche or os.environ.get("CHRYS_STYLES_TRANCHE", "30"))
        self.noms = list(styles or os.environ.get("CHRYS_STYLES_LISTE", ",".join(STYLES)).split(","))
        self.c = float(c if c is not None else os.environ.get("CHRYS_STYLES_C", "0.5"))
        cles = {k for v in STYLES.values() if v for k in v}
        self.base = {k: os.environ.get(k) for k in cles}  # réglages d'origine, remis avant chaque style
        self.journal, self.niveau = [], None
        self._niveau(0)

    def _niveau(self, n):
        self.niveau, self.stats = n, {s: [0, 0.0] for s in self.noms}  # style → [tranches, somme des récompenses]
        self.vues, self.style = set(), None
        self._ouvrir(self.noms[0])

    def _ouvrir(self, style):
        self.style, self.coups, self.nouv, self.der_nouv, self.div0 = style, 0, 0, 0, None
        for k, v in self.base.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in (STYLES[style] or {}).items():
            os.environ[k] = v

    def _choisir(self):
        n = sum(t for t, _ in self.stats.values())
        for s in self.noms:
            if self.stats[s][0] == 0:
                return s
        return max(self.noms, key=lambda s: self.stats[s][1] / self.stats[s][0]
                   + self.c * math.sqrt(math.log(n) / self.stats[s][0]))

    def _fermer(self, divergences):
        r = (self.nouv - 0.5 * (divergences - (self.div0 or 0))) / max(1, self.coups)
        self.stats[self.style][0] += 1
        self.stats[self.style][1] += r
        self.journal.append({"niveau": self.niveau, "style": self.style, "coups": self.coups, "recompense": round(r, 3)})
        self._ouvrir(self._choisir())

    def moteur_actif(self, niveau, grille, divergences, en_plan=False):
        """Appelé à chaque tour de la branche, AVANT le moteur. niveau = niveaux réussis ; grille = image courante ;
        divergences = compteur cumulé de plans démentis ; en_plan : un plan est en cours (on ne change pas de style au
        milieu : la tranche se ferme au premier tour hors plan). → False si le style courant fait taire le moteur."""
        if niveau != self.niveau:
            self._niveau(niveau)
        if self.div0 is None:
            self.div0 = divergences
        h = hashlib.md5(np.asarray(grille).tobytes()).hexdigest()
        if h not in self.vues:
            self.vues.add(h)
            self.nouv += 1
            self.der_nouv = self.coups
        self.coups += 1
        if not en_plan and (self.coups >= self.tranche or self.coups - self.der_nouv >= max(2, self.tranche // 2)):
            self._fermer(divergences)
        return STYLES[self.style] is not None
