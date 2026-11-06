# SPDX-License-Identifier: MIT-0
"""Enfant de la porte v5 (contrat E_PORTE5, Codex 30/10) : un processus par ouverture, lancé par porte_v5.py, sans SDK ni
secret. Il charge la v4 du paquet (poussée, puis fantôme et inventeur) dans SES modules et demande chaque coup au parent par
lignes JSON ; c'est le parent qui joue. Jamais de RESET : une défaite met fin à l'ouverture.
Comparateur (journal seul par défaut ; il ne coupe qu'en strict, amendement du 30/10 13 h 25) : champs réellement prédits par la v4, sans toucher au paquet. Poussée : position de
chaque objet et sélection. Fantôme : position du joueur. Inventeur : au moins une hypothèse d'accord sur joueur, objets, portes.
NON couverts : pixels, compteurs, bits et routes du fantôme. Un écart arrête le plan au coup suivant, sauf réparation sans coup :
immobilité mémorisée (ce que la v4 retient dans `blocked`) ET rejeu de tout le préfixe du niveau avec le modèle courant.
Usage : python -I porte_v5_enfant.py <paquet> <sortie> <budget> <strict 0|1>, état initial en 1re ligne de stdin."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

NOMS = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "UNDO"}


def empreinte(grille):
    return hashlib.sha256(json.dumps(grille, separators=(",", ":")).encode()).hexdigest()[:16]


class Canal:
    def __init__(self):
        self.sortie = os.fdopen(os.dup(1), "w", buffering=1)
        os.dup2(2, 1)  # tout print de la v4 part dans le journal d'erreurs, jamais dans le protocole
        self.entree = sys.stdin

    def dire(self, **m):
        self.sortie.write(json.dumps(m) + "\n")

    def lire(self):
        ligne = self.entree.readline()
        if not ligne:
            os._exit(0)  # parent parti
        return json.loads(ligne)


class Arret(BaseException):
    """Hors Exception : les `except Exception` de la v4 ne doivent pas l'avaler et continuer à jouer."""


SONDE = re.compile(r"identif|experien|explor|discrim|sonde")


def rejouer(pas, prefixe, table):
    """Le modèle courant réexplique-t-il TOUT le préfixe ? prefixe = [(état, action, observé)] ; table = immobilités apprises."""
    for s, a, obs in prefixe:
        try:
            k = (repr(s), a)
            if (table[k] if k in table else pas(s, a)) != obs:
                return False
        except Exception:  # noqa: BLE001 — un modèle qui plante au rejeu n'explique rien
            return False
    return True


class Suivi:
    """Comparateur prédit/observé d'un niveau ; contrôlé avant chaque coup proposé."""

    def __init__(self, canal, strict=True):
        self.canal, self.strict, self.total, self.reparations = canal, strict, 0, 0
        self.en_rejeu, self.en_suivi = False, False
        self.purpose = None
        self.nouveau_niveau()

    def nouveau_niveau(self):
        self.ecart, self.accords, self.niveau_ecarts = None, [], 0

    def noter(self, modele, pas, prec, obs):
        s, a, pred = prec
        d = modele.__dict__
        d.setdefault("_p5_prefixe", []).append((s, a, obs))
        if obs != pred:
            self.total += 1
            self.niveau_ecarts += 1
            self.ecart = (modele, pas, s, a, pred, obs)

    def controler(self):
        """Avant un coup : tout écart en attente est réexpliqué ou arrête le plan."""
        accords, self.accords = self.accords, []
        if accords and not any(accords):
            self.total += 1
            self.niveau_ecarts += 1
            self.canal.dire(t="ecart", famille="inventeur", repare=False)
            if self.strict:
                raise Arret("ecart non reexplique")
        if self.ecart is None:
            return
        modele, pas, s, a, pred, obs = self.ecart
        self.ecart = None
        if not self.strict:
            self.canal.dire(t="ecart", famille=pas.__name__, predit=repr(pred)[:200], observe=repr(obs)[:200])
            return
        immobile = obs is not None and obs == (s[0] if pas.__name__ == "step_state" else s)
        table = modele.__dict__.setdefault("_p5_table", {})
        if immobile:
            table[(repr(s), a)] = obs
        prj = (lambda x, y: pas(modele, x, y)[0]) if pas.__name__ == "step_state" else (lambda x, y: pas(modele, x, y))
        self.en_rejeu = True
        try:
            ok = immobile and rejouer(prj, modele.__dict__["_p5_prefixe"], table)
        finally:
            self.en_rejeu = False
        self.canal.dire(t="ecart", famille=pas.__name__, repare=ok, predit=repr(pred)[:200], observe=repr(obs)[:200],
                        rejoues=len(modele.__dict__["_p5_prefixe"]))
        if not ok:
            raise Arret("ecart non reexplique")
        self.reparations += 1


class _Image:
    def __init__(self, etat):
        self.frame, self.levels_completed = [etat["grille"]], etat["niveaux"]
        self.state, self.available_actions = etat["etat"], etat["dispo"]


class EnvEnfant:
    def __init__(self, canal, etat, suivi):
        self.canal, self.etat, self.n, self.suivi = canal, etat, 0, suivi
        self.sondes = etat.get("sondes", 0)

    def reset(self):
        return _Image(self.etat)  # la partie est déjà en cours : aucun coup dépensé, aucun vrai RESET

    def jouer(self, a):
        if isinstance(a, (list, tuple)) and len(a) == 3:
            act = {"action": "MOUSE", "row": int(a[2]), "col": int(a[1])}
        elif int(a) in NOMS:
            act = {"action": NOMS[int(a)]}
        else:
            raise Arret(f"action refusée : {a!r}")  # RESET compris (contrat : pas de faux nouveau départ)
        self.suivi.controler()
        sonde = bool(SONDE.search(str(self.suivi.purpose or "")))
        if sonde and self.sondes <= 0 and self.suivi.strict:
            raise Arret("sondes epuisees")  # jamais réarmées, ni par un écart ni par un nouveau niveau
        self.sondes -= sonde
        self.n += 1
        self.canal.dire(t="action", n=self.n, sha=empreinte(self.etat["grille"]), action=act, sonde=sonde,
                        niveau=self.etat["niveaux"], obs=self.etat["obs"])
        r = self.canal.lire()
        if r.get("stop"):
            os._exit(0)
        if r["niveaux"] != self.etat["niveaux"] and "sondes" in r:
            self.sondes = r["sondes"]  # le parent seul décide de la portée du budget
        self.etat = r
        return _Image(r)


def _brancher(suivi):
    """Enrobe les modèles v4 : la prédiction du dernier pas, comparée à l'observation qui suit."""
    from agent_p1.agent import Agent
    from agent_p1.labo import LaboP1
    from boucle_v4.fantome_general import FantomeGeneral
    from boucle_v4.poussee_generale import PousseeGenerale

    def enrober(cls, nom_pas, nom_obs, proj):
        pas0, obs0 = getattr(cls, nom_pas), getattr(cls, nom_obs)

        def pas(self, s, a):
            r = pas0(self, s, a)
            if not suivi.en_rejeu:
                self.__dict__["_p5_dernier"] = (s, a, r)
            return r
        pas.__name__ = nom_pas

        def obs(self, image, pred):
            r = obs0(self, image, pred)
            d = self.__dict__.pop("_p5_dernier", None)
            if d is not None and not suivi.en_suivi and d[2] is not None and proj(d[2]) == pred:
                suivi.noter(self, pas, (d[0], d[1], pred), r)
            return r
        setattr(cls, nom_pas, pas)
        setattr(cls, nom_obs, obs)
    enrober(PousseeGenerale, "step", "observe", lambda r: r)
    enrober(FantomeGeneral, "step_state", "observe_player", lambda r: r[0])

    accord0, suivre0, jouer0 = Agent._accord, Agent.avancer_suivi, LaboP1.play

    def accord(self, M, pred, obs):
        r = accord0(self, M, pred, obs)
        suivi.accords.append(bool(r))
        return r

    def suivre(self, t):
        suivi.en_suivi = True
        try:
            return suivre0(self, t)
        finally:
            suivi.en_suivi = False

    def jouer_lab(self, a, purpose="experience"):
        suivi.purpose = purpose
        return jouer0(self, a, purpose)
    Agent._accord, Agent.avancer_suivi, LaboP1.play = accord, suivre, jouer_lab


def jouer(canal, paquet, out, budget, strict, etat):
    sys.path[:0] = [str(paquet), str(paquet / "livraison_p1/code"), str(paquet / "references/astra4/livraison_astra4/ajouts")]
    import types

    import chrysalide.arc3.logique as _logique
    suivi = Suivi(canal, strict)
    env = EnvEnfant(canal, etat, suivi)
    coq = types.ModuleType("chrysalide.arc3.logique.jeux")
    coq.environnement = lambda jeu, dossier=None: env
    coq.jouer_action = lambda e, a: e.jouer(a)
    sys.modules["chrysalide.arc3.logique.jeux"] = coq
    _logique.jeux = coq
    import agent_p1.jouer as J
    from agent_p1.journal import Journal
    from agent_p1.labo import LaboP1
    _brancher(suivi)
    j = Journal(out, "journal_porte", {"budget": budget, "paquet": str(paquet)})
    lab = LaboP1("jeu", 1, None, out / "N1" / "partie")
    lab.completed_baseline = etat["niveaux"]  # défaut v4 corrigé : reprise tardive, compteur réel de niveaux
    gagnes, raison = 0, "?"
    for niveau in range(1, 21):
        od = out / f"N{niveau}"
        suivi.nouveau_niveau()
        r, arret = None, None
        try:
            r = J.essai_poussee(lab, od, budget, j)
            if not lab.won and not lab.finished and len(lab.rows) < budget:  # défaut v4 corrigé : pas de reset après défaite
                r = J.essai_fantome(lab, od, budget, j, out / "bibliotheque.json") or r
        except Arret as e:
            arret, r = str(e), {"agent": "arret", "raison": str(e)}
        except Exception as e:  # noqa: BLE001 — la v4 qui plante rend la main
            r = {"agent": "exception", "raison": repr(e)[:200]}
        canal.dire(t="niveau", niveau=niveau, agent=(r or {}).get("agent"), victoire=bool(lab.won), coups=len(lab.rows),
                   raison=(r or {}).get("raison"), ecarts=suivi.niveau_ecarts)
        if not lab.won:
            raison = arret or ("defaite" if lab.finished else "non reconnu" if r is None else "non gagné")
            break
        gagnes += 1
        if lab.partie_gagnee:
            raison = "partie gagnée"
            break
        lab = lab.next_level(out / f"N{niveau + 1}" / "partie")
    canal.dire(t="fini", niveaux=gagnes, raison=raison, ecarts=suivi.total, reparations=suivi.reparations)


if __name__ == "__main__":
    paquet, out, budget, strict = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4] == "1"
    canal = Canal()
    jouer(canal, paquet, out, budget, strict, canal.lire())
