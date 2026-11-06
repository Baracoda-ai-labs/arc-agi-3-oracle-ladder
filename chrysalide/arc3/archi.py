# SPDX-License-Identifier: MIT-0
"""Architecture Chrysalide pour ARC-AGI-3 (CW-024) : 4 pièces SANS LLM, chacune derrière un interrupteur (variable
d'environnement), à brancher dans le harnais de Franzen (fork Apache-2.0 du Duck). Tous interrupteurs éteints, le harnais
de base est inchangé (contrôle F-C2).
  CHRYS_MONITEUR=1  moniteur permanent : diff d'images, barre/compteur qui décroît, actions sans effet (« signatures
                    mortes », règle de Reki), bloc d'état compact à réinjecter après élagage du contexte ;
  CHRYS_REFLEXES=1  mémoire de réflexes : après un niveau réussi, la séquence d'actions et les fonctions utilisées sont
                    stockées avec préconditions, effet attendu et provenance ;
  CHRYS_ROUTEUR=1   routeur : si un réflexe valide s'applique à l'état courant, ses actions sont jouées SANS appel au modèle ;
  CHRYS_VERIF=1     vérification : après chaque action d'un réflexe, effet prédit contre effet observé ; un écart invalide
                    le réflexe (statut périmé, historique gardé : la mémoire invalidable du jalon 1) et rend la main.
Points de branchement dans le harnais (fichiers de tiers/arc-agi-3-solution/ARC3-Inference/inference/agent/) :
  - avant chaque requête au modèle (tool_agent.py, appel /chat/completions) : Routeur.decider() ;
  - après chaque action exécutée (résultats d'actions dans tool_agent.py) : Moniteur.observer(), Verificateur.verifier() ;
  - à chaque niveau réussi (level_completed) : MemoireReflexes.enregistrer() ;
  - après un élagage du contexte : Moniteur.bloc_etat() est réinjecté."""
import hashlib
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path


def actif(nom):
    return os.environ.get(f"CHRYS_{nom}", "0") == "1"


def diff(g0, g1, bord=4):
    """(cases changées à l'intérieur, cases changées dans la bordure de `bord` cases)."""
    h, w = len(g0), len(g0[0])
    dedans = dehors = 0
    for i in range(h):
        for j in range(w):
            if g0[i][j] != g1[i][j]:
                if bord <= i < h - bord and bord <= j < w - bord:
                    dedans += 1
                else:
                    dehors += 1
    return dedans, dehors


def empreinte(g):
    return hashlib.sha1(json.dumps(g).encode()).hexdigest()[:16]


def traits(g):
    """Préconditions d'un réflexe : couleurs présentes (avec effectif arrondi) — invariantes à la position."""
    c = Counter(v for r in g for v in r)
    return tuple(sorted((k, min(n // 16, 8)) for k, n in c.items()))


# ---------------------------------------------------------------- 1. moniteur (sans LLM)
class Moniteur:
    def __init__(self, bord=4):
        self.bord, self.morts, self.journal, self.niveau = bord, set(), [], 0
        self.actions_niveau = 0

    def observer(self, g0, action, g1, level_completed=False, game_over=False):
        dedans, dehors = diff(g0, g1, self.bord)
        sans_effet = dedans == 0 and not level_completed and not game_over
        if sans_effet:
            self.morts.add((empreinte(g0), json.dumps(action, sort_keys=True)))
        self.actions_niveau += 1
        if level_completed:
            self.niveau, self.actions_niveau = self.niveau + 1, 0
        e = {"action": action, "interieur": dedans, "bordure": dehors, "sans_effet": sans_effet,
             "barre": dehors > 0 and dedans == 0, "fin_niveau": level_completed, "game_over": game_over}
        self.journal.append(e)
        return e

    def deja_mort(self, g, action):
        """Signature morte : cette action, dans cet état exact, n'a déjà rien changé (à éviter)."""
        return (empreinte(g), json.dumps(action, sort_keys=True)) in self.morts

    def bloc_etat(self, n=8):
        """Bloc compact, à réinjecter après élagage : ce que le modèle risque d'avoir perdu."""
        recents = self.journal[-n:]
        lignes = [(f"[ÉTAT CHRYSALIDE] niveau {self.niveau}, actions sur ce niveau {self.actions_niveau}, "
                   f"signatures mortes {len(self.morts)}")]
        for e in recents:
            effet = ("niveau réussi" if e["fin_niveau"] else "game over" if e["game_over"] else
                     "sans effet" if e["sans_effet"] else f"{e['interieur']} cases changées")
            lignes.append(f"- {e['action']} -> {effet}" + (" (la bordure seule a changé : barre ?)" if e["barre"] else ""))
        return "\n".join(lignes)


# ---------------------------------------------------------------- 2. mémoire de réflexes
@dataclass
class Reflexe:
    id: str
    preconditions: list            # traits() de l'état de départ
    actions: list                  # séquence jouée qui a fini le niveau
    effets: list                   # (intérieur changé > 0 ?) attendu après chaque action
    fonctions: dict = field(default_factory=dict)   # nom -> source des fonctions Python retenues
    provenance: dict = field(default_factory=dict)  # jeu, niveau, passage, horodatage
    statut: str = "actif"
    historique: list = field(default_factory=list)


class MemoireReflexes:
    def __init__(self, chemin=None):
        self.chemin, self.reflexes = (Path(chemin) if chemin else None), {}
        if self.chemin and self.chemin.exists():
            self.reflexes = {k: Reflexe(**v) for k, v in json.loads(self.chemin.read_text()).items()}

    def enregistrer(self, g_depart, journal_niveau, fonctions=None, provenance=None):
        actions = [e["action"] for e in journal_niveau]
        effets = [not e["sans_effet"] for e in journal_niveau]
        rid = hashlib.sha1(json.dumps([traits(g_depart), actions]).encode()).hexdigest()[:12]
        self.reflexes[rid] = Reflexe(rid, list(traits(g_depart)), actions, effets, fonctions or {}, provenance or {})
        self.sauver()
        return rid

    def candidats(self, g):
        t = list(traits(g))
        return [r for r in self.reflexes.values() if r.statut == "actif" and r.preconditions == t]

    def invalider(self, rid, raison):
        r = self.reflexes[rid]
        r.historique.append({"statut": r.statut, "raison": raison})
        r.statut = "perime"
        self.sauver()

    def sauver(self):
        if self.chemin:
            self.chemin.write_text(json.dumps({k: asdict(v) for k, v in self.reflexes.items()}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 3. routeur et 4. vérification
class Routeur:
    """decider(g) -> ("reflexe", r) si un réflexe valide s'applique, sinon ("deliberer", None). Aucun appel au modèle."""
    def __init__(self, memoire, moniteur=None):
        self.memoire, self.moniteur, self.en_cours, self.pas = memoire, moniteur, None, 0
        self.n_sans_llm = self.n_deliberations = 0

    def decider(self, g):
        if not actif("ROUTEUR"):
            return ("deliberer", None)
        if self.en_cours is None:
            c = self.memoire.candidats(g)
            if not c:
                self.n_deliberations += 1
                return ("deliberer", None)
            self.en_cours, self.pas = c[0], 0
        if self.pas >= len(self.en_cours.actions):
            self.en_cours = None
            self.n_deliberations += 1
            return ("deliberer", None)
        a = self.en_cours.actions[self.pas]
        if self.moniteur is not None and self.moniteur.deja_mort(g, a):
            self.en_cours = None
            self.n_deliberations += 1
            return ("deliberer", None)
        self.pas += 1
        self.n_sans_llm += 1
        return ("reflexe", a)


class Verificateur:
    def __init__(self, memoire, routeur):
        self.memoire, self.routeur, self.n_invalides = memoire, routeur, 0

    def verifier(self, effet_observe):
        """Après une action de réflexe : effet attendu (changement intérieur oui/non) contre effet observé."""
        r = self.routeur.en_cours
        if not actif("VERIF") or r is None:
            return True
        attendu = r.effets[self.routeur.pas - 1]
        observe = not effet_observe["sans_effet"]
        if attendu != observe or effet_observe["game_over"]:
            self.memoire.invalider(r.id, f"pas {self.routeur.pas} : attendu changement={attendu}, observé={observe}"
                                         + (", game over" if effet_observe["game_over"] else ""))
            self.n_invalides += 1
            self.routeur.en_cours = None
            return False
        return True
