# SPDX-License-Identifier: MIT-0
"""`demander_qwen` — colonne vertébrale des questions du moteur à Qwen (CW-357, bornes de CW-358, boucle Mac de CW-360).
- Une question = un TYPE (« regle », « but », « exploration », « fiche », « economie » de F) + un DOSSIER (dict JSON : scène neutre, menu
  opérationnel, contrat ; fabriqué par C, E, D…). La réponse est CONTRAINTE par un petit schéma JSON (énumérations fermées,
  « insuffisant » toujours permis), puis convertie de façon déterministe en `Reponse` de la langue unique (docs/LANGUE_PYTHON.md
  § 8) : jamais de texte libre interprété, jamais d'exécution.
- Bornes : sans réflexion par défaut, 256 jetons, délai maximal, sortie tronquée = abstention ; UNE requête moteur à la fois
  (file à un seul ouvrier) ; plafond par jeu (4) et global ; cache indexé par la signature (type, modèle, dossier) ; journal JSONL.
- Serveurs : « ollama » (Mac, `qwen3.8:27b-mlx`, `qwen3:4b`…) ou « sglang » (pod, API OpenAI, `flashnext`). Un résultat Mac
  ne vaut pas résultat pod (CW-360) : le serveur et le modèle sont écrits dans chaque entrée du journal."""
import base64
import hashlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ABSTENTIONS = ("insuffisant", "aucun")
_FILE = ThreadPoolExecutor(max_workers=1)  # une seule requête moteur à la fois sur tout le serveur (CW-358)
_VERROU = threading.Lock()
_CACHE, _COMPTES = {}, {"global": 0}
JOURNAL_DEFAUT = Path(__file__).resolve().parents[2] / "experiments/demander_qwen/journal.jsonl"
SERVEURS = {"ollama": "http://127.0.0.1:11434", "sglang": os.environ.get("CHRYS_QWEN_URL", "http://127.0.0.1:8011/v1")}


def actif():
    """Drapeau d'intégration (CW-362.2) : ÉTEINT par défaut ; `CHRYS_QWEN=1` dans le carnet Kaggle ou au pod pour l'allumer.
    Serveur et modèle par défaut : `CHRYS_QWEN_SERVEUR` (« sglang » au pod / Kaggle), `CHRYS_QWEN_MODELE` (« flashnext »)."""
    return os.environ.get("CHRYS_QWEN") == "1"


def reglages():
    return {"serveur": os.environ.get("CHRYS_QWEN_SERVEUR", "sglang"), "modele": os.environ.get("CHRYS_QWEN_MODELE", "flashnext"),
            "delai_s": float(os.environ.get("CHRYS_QWEN_DELAI", "60"))}
# D (CW-362.2) : dans le carnet, notre cellule pose CHRYS_QWEN_SERVEUR=sglang, CHRYS_QWEN_URL = SERVER_BASE_URL (port 8001)
# et CHRYS_QWEN_MODELE = SERVED_MODEL_NAME du v3 ; l'adresse est relue à CHAQUE appel (« kaggle » = autre nom de « sglang »).
PREFIXE = ("Tu aides un moteur qui apprend un jeu vidéo sur grille en l'observant. Le moteur te pose UNE question fermée. "
           "Réponds UNIQUEMENT par l'objet JSON demandé, valeurs prises dans les listes données. Choisis « insuffisant » "
           "seulement si aucune valeur de la liste n'est compatible avec ce qui est montré.\n")


# ------------------------------------------------------------------ schémas par type (énumérations fermées)
def schema(type_, dossier):
    menu = list((dossier.get("menu") or {}).keys())
    ids = [o["id"] for o in dossier.get("scene", []) if "id" in o]
    # Pas de champ « statut » en tête (21/10, boucle Mac) : généré en premier, il engageait le modèle sur « insuffisant »
    # AVANT le choix (8/8 abstentions, avec un candidat rempli quand même). L'abstention est une valeur du choix lui-même.
    if type_ == "regle":
        return {"type": "object", "required": ["candidat", "objets", "experience"], "properties": {
            "candidat": {"type": "string", "enum": menu + list(ABSTENTIONS)},
            "objets": {"type": "array", "items": {"type": "string", "enum": ids}, "maxItems": 4},
            "experience": {"type": "string", "maxLength": 160}}}
    if type_ == "but":
        return {"type": "object", "required": ["forme", "objets", "departage"], "properties": {
            "forme": {"type": "string", "enum": menu + list(ABSTENTIONS)},
            "objets": {"type": "array", "items": {"type": "string", "enum": ids}, "maxItems": 4},
            "departage": {"type": "string", "maxLength": 160}}}
    if type_ == "exploration":
        cands = [c["id"] for c in dossier.get("candidats", [])] or ids
        return {"type": "object", "required": ["objet"], "properties": {
            "objet": {"type": "string", "enum": cands + list(ABSTENTIONS)}}}
    if type_ == "economie":  # F (CW-357, impasse économie) : quelles actions coûtent ? (barème de la fiche, `economie.cout`)
        return {"type": "object", "required": ["cout"], "properties": {
            "cout": {"type": "string", "enum": list(dossier.get("menu") or {}) + list(ABSTENTIONS)}}}
    if type_ == "fiche":
        return {"type": "object", "required": list(dossier["valeurs"]), "properties": {
            k: {"type": "string", "enum": list(v) + ["insuffisant"]} for k, v in dossier["valeurs"].items()}}
    raise ValueError(f"type de question inconnu : {type_}")


def invite(type_, dossier):
    """Préfixe commun identique pour toutes les questions (cache de préfixe du serveur), puis le dossier en JSON compact."""
    corps = {k: v for k, v in dossier.items() if k not in ("images", "_verite")}
    return PREFIXE + f"Type de question : {type_}.\n" + json.dumps(corps, ensure_ascii=False, separators=(",", ":"))


# ------------------------------------------------------------------ réponse → langue unique (déterministe)
def vers_reponse(type_, brut, dossier):
    """JSON du modèle → {"statut": "propose" | "abstention" | "illisible", "choix": …, "langue": texte § 8}."""
    try:
        r = json.loads(brut)
    except (ValueError, TypeError):
        return {"statut": "illisible", "raison": "JSON invalide"}
    sch = schema(type_, dossier)
    for k in sch["required"]:
        if k not in r:
            return {"statut": "illisible", "raison": f"clé {k} absente"}
        en = sch["properties"][k].get("enum")
        if en and r[k] not in en:
            return {"statut": "illisible", "raison": f"{k}={r[k]!r} hors liste"}
    if type_ == "fiche":
        choix = {k: v for k, v in r.items() if k in sch["properties"]}
        return {"statut": "propose", "choix": choix, "langue": f"REPONSE = Fiche({json.dumps(choix, ensure_ascii=False)})"}
    cle = {"regle": "candidat", "but": "forme", "exploration": "objet", "economie": "cout"}[type_]
    if r[cle] in ABSTENTIONS:
        return {"statut": "abstention", "choix": None, "langue": 'REPONSE = Abstention(raison="insuffisant")'}
    choix = {"cle": r[cle], **{k: r[k] for k in ("objets", "experience", "departage") if k in r}}
    return {"statut": "propose", "choix": choix,
            "langue": f"REPONSE = Choix({', '.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in choix.items())})"}


# ------------------------------------------------------------------ appel au serveur
def _appel(serveur, modele, texte, sch, max_tokens, delai_s, reflexion, images):
    import requests
    if serveur == "ollama":
        msg = {"role": "user", "content": texte}
        if images:
            msg["images"] = [base64.b64encode(b).decode() for b in images]
        corps = {"model": modele, "messages": [msg], "format": sch, "stream": False, "think": bool(reflexion),
                 "keep_alive": "2m", "options": {"temperature": 0.0, "num_predict": max_tokens + (reflexion or 0)}}
        rep = requests.post(f"{SERVEURS['ollama']}/api/chat", json=corps, timeout=delai_s).json()
        return (rep.get("message") or {}).get("content", ""), rep.get("done_reason"), {
            "entree": rep.get("prompt_eval_count"), "sortie": rep.get("eval_count")}
    contenu = [{"type": "text", "text": texte}] + [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b).decode()}} for b in images or []]
    corps = {"model": modele, "messages": [{"role": "user", "content": contenu if images else texte}], "temperature": 0.0,
             "max_tokens": max_tokens + (reflexion or 0), "chat_template_kwargs": {"enable_thinking": bool(reflexion)},
             "response_format": {"type": "json_schema", "json_schema": {"name": "reponse", "schema": sch}}}
    base = os.environ.get("CHRYS_QWEN_URL") or SERVEURS["sglang"]
    rep = requests.post(f"{base.rstrip('/')}/chat/completions", json=corps, timeout=delai_s).json()
    ch = rep["choices"][0]
    return ch["message"].get("content") or "", ch.get("finish_reason"), rep.get("usage")


def demander_qwen(type_, dossier, *, jeu=None, serveur=None, modele="qwen3.8:27b-mlx", max_tokens=256, delai_s=90,
                  reflexion=0, images=(), plafond_jeu=4, plafond_global=200, journal=JOURNAL_DEFAUT, cache=True):
    """→ {"statut": "propose" | "abstention" | "illisible" | "plafond" | "erreur", "choix", "langue", "latence_s", …}."""
    serveur = serveur or os.environ.get("CHRYS_QWEN_SERVEUR", "ollama")
    if serveur in ("sglang", "kaggle") and modele == "qwen3.8:27b-mlx":  # nom du Mac : remplacé par celui du serveur
        modele = os.environ.get("CHRYS_QWEN_MODELE", "flashnext")
    if journal == JOURNAL_DEFAUT and os.environ.get("CHRYS_DOSSIER"):  # carnet : le journal va avec nos traces
        journal = Path(os.environ["CHRYS_DOSSIER"]) / "demander_qwen.jsonl"
    sch = schema(type_, dossier)
    texte = invite(type_, dossier)
    sig = hashlib.sha256(json.dumps([type_, serveur, modele, reflexion, texte,
                                     [hashlib.sha256(b).hexdigest() for b in images]]).encode()).hexdigest()[:16]
    with _VERROU:
        if cache and sig in _CACHE:
            return {**_CACHE[sig], "cache": True}
        if _COMPTES.get(jeu, 0) >= plafond_jeu or _COMPTES["global"] >= plafond_global:
            return {"statut": "plafond", "signature": sig}
        _COMPTES[jeu] = _COMPTES.get(jeu, 0) + 1
        _COMPTES["global"] += 1
    t0 = time.time()
    try:
        brut, fin, usage = _appel(serveur, modele, texte, sch, max_tokens, delai_s, reflexion, images)
        out = {"statut": "abstention", "raison": "sortie tronquée"} if fin == "length" else vers_reponse(type_, brut, dossier)
        out.update(brut=brut[:600], fin=fin, usage=usage)
    except Exception as ex:  # noqa: BLE001 — délai dépassé, serveur absent : compté, jamais propagé au moteur
        out = {"statut": "erreur", "raison": repr(ex)[:200]}
    out.update(latence_s=round(time.time() - t0, 2), signature=sig, type=type_, serveur=serveur, modele=modele, jeu=jeu,
               reflexion=reflexion, n_images=len(images))
    if out["statut"] in ("propose", "abstention"):
        with _VERROU:
            _CACHE[sig] = out
    if journal:
        Path(journal).parent.mkdir(parents=True, exist_ok=True)
        with open(journal, "a") as h:
            h.write(json.dumps({"t": time.time(), **{k: v for k, v in out.items() if k != "brut"}}, ensure_ascii=False) + "\n")
    return out


def demander_qwen_async(*args, **kw):
    """Même chose, en fond : rend un Future (file à un seul ouvrier). Le moteur l'utilise s'il arrive à temps, sinon l'ignore."""
    return _FILE.submit(demander_qwen, *args, **kw)


def invalider(signature=None):
    """Observation contraire : on retire une réponse du cache (ou tout le cache)."""
    with _VERROU:
        if signature is None:
            _CACHE.clear()
        else:
            _CACHE.pop(signature, None)
