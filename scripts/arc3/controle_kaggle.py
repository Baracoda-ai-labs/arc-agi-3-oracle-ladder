# SPDX-License-Identifier: MIT-0
"""F (CW-429, CW-431, CW-432) : contrôle d'une exécution Kaggle SANS GPU, sur ses journaux. OK ou KO selon cinq points :
  1. serveur prêt (et en combien de secondes) : « READY after Ns » du carnet de Franzen (cellule 12), « fired up » de
     serve.log ; KO si « DEADLINE at Ns … still loading » ou si rien ne dit « prêt » ;
  2. jeux à 0 action : résumé de fin de passage (« <jeu>: score=…, actions=N, tokens=N ») ; KO si un jeu a 0 action ou si
     le total vaut 0 ; « absent » (KO) si le résumé manque ;
  3. environnement : AVERTISSEMENT seulement, jamais KO. CW-432 : la version à 28,21 affiche aussi « Latest Container
     Image », le libellé ne prouve donc rien. On l'affiche, avec l'épinglage s'il est lu (Logs ou --environnement) ;
  4. erreurs : Traceback, CUDA error, Killed, out of memory, NCCL, « Connection refused » APRÈS le « prêt » ;
  5. témoins (CW-431) : KO si l'un des jeux vc33, tu93, wa30, s5i5, cn04 apparaît comme joué (« vc33-xxxxxxxx »).
Point « démarrage » (CCM-095-D, carnet R0 et suivants) : lu dans `chrysalide_demarrage.jsonl` (--demarrage) ou dans les
lignes « CHRYSALIDE démarrage <étape> {…} » des Logs. KO si pas de `premiere_inference`, si `python_312` est faux, ou si
`serveur_mort` ou `echec` apparaît ; sans objet si le carnet n'a pas cette vérification.
--moteur-seul (carnet CPU du moteur, `kaggle/notebook_moteur_seul.ipynb`, CCM-085-D) : pas de serveur ni de résumé Franzen.
  1. paquet : KO sans « paquet conforme : global … » (ou si « archive corrompue », « modifié : », « empreinte globale ») ;
  2. jeux : ligne finale « jeux joués X / Y ; niveaux N ; erreurs E » ; KO si absente, X < Y ou N = 0 ; avec --pilote
     (moteur_seul/pilote.jsonl) : KO aussi sur tout jeu « saute » ;
  5. témoins : KO aussi sur « GARDE TÉMOINS » ou « TemoinInterdit » (la garde a dû s'arrêter : rien n'est sûr).
Formats lus : texte brut, ou le fichier « Download logs » de Kaggle (liste JSON de {"stream_name", "time", "data"}).
Usage : uv run python scripts/arc3/controle_kaggle.py <Logs> [--serve serve.log] [--environnement "texte de l'en-tête"]
        [--demarrage chrysalide_demarrage.jsonl] [--moteur-seul [--pilote moteur_seul/pilote.jsonl]]
Sortie : un bloc lisible + une ligne finale « VERDICT : OK » ou « VERDICT : KO (…) » ; code de retour 0 si OK, 1 sinon."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ERREURS = re.compile(r"Traceback \(most recent call last\)|CUDA error|\bKilled\b|out of memory|OutOfMemory|NCCL error"
                     r"|Segmentation fault|core dumped")
REFUS = re.compile(r"Connection refused|ConnectionRefused|Max retries exceeded")
JEU = re.compile(r"^\s*([a-z0-9]{4}-[0-9a-f]{8}): score=([\d.]+), levels=([\d.]+)/(\d+), actions=(\d+), tokens=(\d+)")
HORO = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]")
TEMOINS = re.compile(r"\b(vc33|tu93|wa30|s5i5|cn04)-[0-9a-f]{8}")  # jeux tenus à l'écart (CLAUDE.md, gel du 27)


def lignes(chemin):
    """Texte brut, ou export JSON de Kaggle (une entrée par écriture, possiblement plusieurs lignes chacune)."""
    t = Path(chemin).read_text(errors="replace")
    s = t.lstrip()
    if s.startswith("["):
        try:
            return "".join(str(e.get("data", "")) for e in json.loads(s) if isinstance(e, dict)).splitlines()
        except json.JSONDecodeError:
            pass
    return t.splitlines()


def serveur(logs, serve):
    pret = next((i for i, x in enumerate(logs) if "READY after" in x), None)
    if pret is not None:
        s = int(re.search(r"READY after (\d+)s", logs[pret]).group(1))
        return {"ok": True, "detail": f"prêt en {s} s (carnet)", "ligne": pret}
    dl = next((x.strip() for x in logs if "DEADLINE at" in x), None)
    if serve:
        h = [HORO.match(x) for x in serve]
        h = [datetime.fromisoformat(m.group(1)) for m in h if m]
        feu = next((x for x in serve if "fired up" in x), None)
        if feu and h:
            t = (datetime.fromisoformat(HORO.match(feu).group(1)) - h[0]).total_seconds()
            msg = f"serve.log : prêt {t:.0f} s après sa première ligne"
            return {"ok": dl is None, "detail": msg + (" MAIS le carnet a lâché avant (" + dl + ")" if dl else ""),
                    "ligne": None}
        if h:
            return {"ok": False, "detail": f"serve.log : jamais « fired up » ; dernière ligne horodatée {h[-1]} "
                                           f"({(h[-1] - h[0]).total_seconds():.0f} s après la première)"
                                           + (f" ; {dl}" if dl else ""), "ligne": None}
    return {"ok": False, "detail": dl or "aucune ligne « READY after » ni « DEADLINE » : serveur jamais signalé prêt",
            "ligne": None}


def jeux(logs):
    # le résumé est réécrit à chaque sauvegarde périodique (R12 : 5 fois) : seule la DERNIÈRE ligne d'un jeu compte
    der = {}
    for m in filter(None, map(JEU.match, logs)):
        der[m.group(1)] = (m.group(1), int(m.group(5)), int(m.group(6)), float(m.group(2)))
    js = list(der.values())
    if not js:
        return {"ok": False, "detail": "résumé de fin absent (passage interrompu, ou soumission réelle sans résumé)"}
    zero = [j for j, a, _, _ in js if a == 0]
    tot = sum(a for _, a, _, _ in js)
    moy = sum(s for *_, s in js) / len(js)
    return {"ok": not zero and tot > 0, "detail": f"{len(js)} jeux, {tot} actions, score moyen {moy:.2f} ; "
                                                  f"{len(zero)} à 0 action" + (f" ({', '.join(zero[:6])}…)" if zero else "")}


def environnement(logs, texte):
    tout = "\n".join(logs) + "\n" + (texte or "")
    vers = sorted(set(re.findall(r"\b(sglang[ =]+[\d.]+\w*|torch[ =]+[\d.]+\+?\w*)", tout)))[:4]
    v = f" ; versions vues : {', '.join(vers)}" if vers else ""
    if re.search(r"original environment|Pin to original|Pinned", tout, re.IGNORECASE):
        return {"ok": True, "detail": "épinglé sur l'environnement d'origine" + v}
    if re.search(r"Latest Container Image", tout, re.IGNORECASE):
        return {"ok": True, "alerte": True, "detail": "« Latest Container Image » (non bloquant : la version à 28,21 "
                                                      "l'affiche aussi, CW-432)" + v}
    return {"ok": True, "alerte": True, "detail": "environnement non lu dans les journaux (non bloquant ; passer "
                                                  "l'en-tête de la page avec --environnement)" + v}


def erreurs(logs, serve, depuis):
    e = [x.strip()[:160] for x in logs + serve if ERREURS.search(x)]
    r = sum(1 for x in logs[(depuis or 0) + 1 if depuis is not None else 0:] if REFUS.search(x))
    ok = not e and r == 0
    d = f"{len(e)} ligne(s) d'erreur" + (f" (1re : {e[0]})" if e else "") + f" ; {r} « Connection refused »" + \
        (" après le « prêt »" if depuis is not None else "")
    return {"ok": ok, "detail": d}


def temoins(logs, pilote=()):
    vus = sorted({m.group(0) for x in logs for m in TEMOINS.finditer(x)} |
                 {str(r.get("jeu")) for r in pilote if str(r.get("jeu"))[:4] in ("vc33", "tu93", "wa30", "s5i5", "cn04")})
    garde = any("GARDE TÉMOINS" in x or "TemoinInterdit" in x for x in logs)
    if vus or garde:
        return {"ok": False, "detail": (f"JOUÉS : {', '.join(vus)} (brûlés avant le 27)" if vus else "")
                + (" ; garde des témoins déclenchée (exécution arrêtée)" if garde else "")}
    return {"ok": True, "detail": "aucun témoin joué"}


def demarrage(logs, journal=()):
    """Étapes de la vérification de démarrage (scripts/arc3/demarrage_kaggle.py) : {étape: texte de la ligne}."""
    et = {}
    for e in journal:
        et.setdefault(e.get("etape"), json.dumps(e, ensure_ascii=False))
    for x in logs:
        m = re.search(r"CHRYSALIDE démarrage (\w+) (.*)", x)
        if m:
            et.setdefault(m.group(1), m.group(2))
    if not et:
        return {"ok": True, "detail": "sans objet (carnet sans vérification de démarrage)"}
    ko = []
    if "premiere_inference" not in et:
        ko.append("pas de première inférence")
    env = et.get("environnement", "")
    if re.search(r"""['"]python_312['"]: (False|false)""", env):
        ko.append("Python ≠ 3.12")
    for k in ("serveur_mort", "echec"):
        if k in et:
            ko.append(k)
    if ko:
        return {"ok": False, "detail": " ; ".join(ko)}
    lat = re.search(r"""['"]latence_s['"]: ([\d.]+)""", et["premiere_inference"])
    t = re.search(r"""['"]t_s['"]: ([\d.]+)""", et["premiere_inference"])
    return {"ok": True, "detail": f"première inférence à {t.group(1) if t else '?'} s (latence {lat.group(1) if lat else '?'} s)"}


def paquet(logs):
    casse = next((x.strip()[:160] for x in logs if re.search(r"archive corrompue|modifié : |empreinte globale", x)), None)
    ok = next((x.strip()[:120] for x in logs if "paquet conforme : global" in x), None)
    if casse or not ok:
        return {"ok": False, "detail": casse or "aucune ligne « paquet conforme » : paquet non vérifié", "ligne": None}
    return {"ok": True, "detail": ok, "ligne": None}


def jeux_moteur(logs, pilote=()):
    m = None
    for x in logs:
        m = re.search(r"jeux joués (\d+) / (\d+) ; niveaux (\d+) ; erreurs (\d+)", x) or m
    if not m:
        return {"ok": False, "detail": "ligne finale « jeux joués X / Y » absente (carnet interrompu)"}
    x, y, n, e = map(int, m.groups())
    saute = [r.get("jeu") for r in pilote if "saute" in r]
    d = f"{x} / {y} joués, {n} niveaux, {e} erreurs" + (f" ; {len(saute)} sautés ({', '.join(map(str, saute[:5]))})"
                                                       if saute else "")
    return {"ok": x == y and y > 0 and n > 0 and not saute, "detail": d}


def controler(logs, serve=(), texte_env=None, moteur_seul=False, pilote=(), journal=()):
    if moteur_seul:
        points = {"paquet": paquet(logs), "jeux": jeux_moteur(logs, pilote),
                  "environnement": environnement(logs, texte_env), "erreurs": erreurs(logs, [], None),
                  "temoins": temoins(logs, pilote)}
        ko = [k for k, v in points.items() if not v["ok"]]
        return points, ("OK" if not ko else f"KO ({', '.join(ko)})")
    s = serveur(logs, list(serve))
    points = {"serveur": s, "demarrage": demarrage(logs, journal), "jeux": jeux(logs),
              "environnement": environnement(logs, texte_env), "erreurs": erreurs(logs, list(serve), s["ligne"]),
              "temoins": temoins(logs)}
    ko = [k for k, v in points.items() if not v["ok"]]
    return points, ("OK" if not ko else f"KO ({', '.join(ko)})")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("logs")
    p.add_argument("--serve")
    p.add_argument("--environnement")
    p.add_argument("--moteur-seul", action="store_true")
    p.add_argument("--pilote")
    p.add_argument("--demarrage")
    a = p.parse_args(argv)
    pil = [json.loads(x) for x in lignes(a.pilote) if x.strip()] if a.pilote else ()
    jd = [json.loads(x) for x in lignes(a.demarrage) if x.strip()] if a.demarrage else ()
    points, verdict = controler(lignes(a.logs), lignes(a.serve) if a.serve else (), a.environnement, a.moteur_seul, pil,
                                jd)
    for k, v in points.items():
        print(f"{'KO' if not v['ok'] else '!!' if v.get('alerte') else 'OK'}  {k:<14} {v['detail']}")
    print(f"VERDICT : {verdict}")
    return 0 if verdict == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
