# SPDX-License-Identifier: MIT-0
"""Politique scriptée SANS LLM pour le banc hors ligne (CW-032) : teste la mécanique graphe/BFS en boucle fermée.
Modes : "hasard" (référence), "local" (coup non testé de l'état courant, sinon hasard), "graphe" (local + plus court chemin
vers la frontière), "retour" (local + après une mort, plus court chemin connu vers l'état d'avant le coup fatal : ce que V2
fera avec le modèle à la place de « local »). Tout plan est rejoué pas à pas avec vérification (observé ≠ prévu → abandon).
Chaque coup est étiqueté par sa source : "nouveau" (le modèle devrait le choisir), "route" (jouable sans modèle), "hasard"."""
import random

from chrysalide.arc3.graphe import Graphe, candidats, etat


class Explorateur:
    def __init__(self, mode="graphe", graine=0):
        self.mode, self.rng, self.g = mode, random.Random(graine), Graphe()
        self.plan, self.attendu = [], None
        self.n_surprises, self.cible = 0, None

    def choisir(self, grille, niveau, dispo):
        s = etat(grille, niveau)
        cands = candidats(grille, dispo)
        self.g.voir(s, cands)
        if self.attendu is not None and self.attendu != s:  # vérification : le plan ne tient plus
            self.plan, self.n_surprises = [], self.n_surprises + 1
        self.attendu = None
        if self.mode == "hasard":
            return self.rng.choice(cands), "hasard", s
        if self.mode == "retour" and self.cible is not None and not self.plan:
            chemin = self.g.replay_to(s, self.cible)
            self.cible = None
            if chemin:
                self.plan = chemin
        if self.plan:
            k = self.plan.pop(0)
            self.attendu = self.g.prevision(s, k)
            return k, "route", s
        nt = self.g.non_testes(s)
        if nt:
            simples = [k for k in nt if not k.startswith("6@")]
            return self.rng.choice(simples or nt), "nouveau", s
        if self.mode == "graphe":
            chemin = self.g.frontier_path(s)
            if chemin:
                self.plan = chemin[1:]
                self.attendu = self.g.prevision(s, chemin[0])
                return chemin[0], "route", s
        sans_mort = [k for k in cands if not self.g.is_known_dead(s, k)] or cands
        return self.rng.choice(sans_mort), "hasard", s

    def apprendre(self, s0, k, grille1, niveau1, mort):
        self.g.noter(s0, k, etat(grille1, niveau1), mort=mort)
        if mort:
            self.cible, self.plan = s0, []
