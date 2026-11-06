# SPDX-License-Identifier: MIT-0
"""D (CW-446, CW-455 : « notre propre vérification du démarrage Kaggle ») : deux cellules pour le carnet v3 de Franzen,
insérées par `faire_notebook_S.py` (variantes à clé `demarrage`). Aucun réglage de Franzen n'est touché, hormis la durée
de jeu, réduite du temps d'attente (sinon les 9 h du carnet seraient dépassées et la session tuée).
Cellule AVANT la partie (après la cellule 16 de Franzen, avant « Starting benchmark ») — séquence journalisée dans
/kaggle/working/chrysalide_demarrage.jsonl et imprimée (lignes « CHRYSALIDE démarrage ») :
  1. environnement : Python (les roues du serveur sont cp312), versions sglang / torch / arc-agi, carte, variables KAGGLE_* ;
  2. chargement des poids : progression lue dans serve.log (« x/38 ») ;
  3. serveur sain : /health = 200 ;
  4. PREMIÈRE INFÉRENCE réussie (une vraie requête de chat, /health ne suffit pas) ;
  patience CHRYS_PATIENCE_S (défaut 2 h depuis le début du carnet) ; serveur mort = on n'attend plus.
  Pas de « ping » de jeu : tant que la partie n'est pas lancée, aucune feuille de score n'existe (taaf l'ouvre au premier
  jeu), donc rien ne peut être fermé par la passerelle pour inactivité (CW-446) ; aucune action n'est dépensée.
Cellule APRÈS la partie : 5. fin de la partie (durée), pour le contrôle de F (`controle_kaggle.py`)."""

AVANT = r'''# CHRYSALIDE — vérification du démarrage (D, CW-446 / CW-455). Lisible : scripts/arc3/demarrage_kaggle.py
import importlib.metadata as _md, json as _json, os as _os, re as _re, subprocess as _sp, sys as _sys, time as _t
import urllib.request as _ur
_J = Path(WORKING_DIR) / "chrysalide_demarrage.jsonl"
_T0 = globals().get("NOTEBOOK_START_TIME", _t.time())
def _noter(etape, **k):
    ligne = {"etape": etape, "t_s": round(_t.time() - _T0, 1), **k}
    with open(_J, "a") as _f:
        _f.write(_json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
    print("CHRYSALIDE démarrage", etape, {x: y for x, y in ligne.items() if x != "etape"}, flush=True)
def _version(p):
    try:
        return _md.version(p)
    except Exception:
        return None
# 1. environnement
try:
    _gpu = _sp.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True,
                   text=True, timeout=20).stdout.strip()
except Exception as _e:
    _gpu = repr(_e)
_noter("environnement", python=_sys.version.split()[0], python_312=_sys.version_info[:2] == (3, 12),
       sglang=_version("sglang"), torch=_version("torch"), arc_agi=_version("arc-agi"), gpu=_gpu,
       kaggle={k: v for k, v in _os.environ.items() if k.startswith("KAGGLE_") and "TOKEN" not in k and "KEY" not in k},
       true_submission=TRUE_SUBMISSION)
# 2 à 4. chargement, santé, première inférence
_PATIENCE = float(_os.environ.get("CHRYS_PATIENCE_S", str(2 * 3600)))
_base = f"http://127.0.0.1:{SERVED_MODEL_PORT}"
_log = Path(globals().get("LOG", str(Path(WORKING_DIR) / "serve.log")))
_progres, _sain, _pret, _dernier, _txt = None, False, False, 0.0, ""
while _t.time() - _T0 < _PATIENCE:
    try:
        _txt = _log.read_text(errors="replace")[-200000:] if _log.exists() else ""
        _m = _re.findall(r"(\d+)/(\d+) \[", _txt) or _re.findall(r"shards?:?\s*\S*\s*(\d+)/(\d+)", _txt)
        if _m and _m[-1] != _progres:
            _progres = _m[-1]
            _noter("chargement", fait=int(_progres[0]), total=int(_progres[1]))
    except Exception:
        pass
    _p = globals().get("proc")
    if _p is not None and _p.poll() is not None:
        _noter("serveur_mort", code=_p.returncode, fin_du_journal=_txt[-1500:])
        break
    if not _sain:
        try:
            with _ur.urlopen(f"{_base}/health", timeout=5) as _r:
                _sain = _r.status == 200
            if _sain:
                _noter("sante", statut=200)
        except Exception:
            pass
    if _sain:
        _corps = {"model": SERVED_MODEL_NAME, "messages": [{"role": "user", "content": "Reply with the single word OK."}],
                  "max_tokens": 16, "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}
        _d = _t.time()
        try:
            _req = _ur.Request(f"{_base}/v1/chat/completions", data=_json.dumps(_corps).encode(),
                               headers={"Content-Type": "application/json"})
            with _ur.urlopen(_req, timeout=180) as _r:
                _rep = _json.loads(_r.read())
            _msg = (_rep.get("choices") or [{}])[0].get("message") or {}
            _txt_rep = (_msg.get("content") or _msg.get("reasoning_content") or "")
            _n = (_rep.get("usage") or {}).get("completion_tokens") or 0
            if _txt_rep.strip() or _n > 0:
                _pret = True
                _noter("premiere_inference", latence_s=round(_t.time() - _d, 2), jetons=_n, extrait=_txt_rep[:40])
                break
            _noter("inference_vide", reponse=str(_rep)[:300])
        except Exception as _e:
            if _t.time() - _dernier > 120:
                _noter("inference_en_echec", erreur=repr(_e)[:200])
                _dernier = _t.time()
    if _t.time() - _dernier > 300:
        _noter("attente", sain=_sain, chargement=_progres)
        _dernier = _t.time()
    _t.sleep(10)
if not _pret:
    _noter("echec", patience_s=_PATIENCE, sain=_sain, chargement=_progres)
# durée de jeu : jamais au-delà des 9 h du carnet (32 400 s), marge 15 min
try:
    _reste = 32400.0 - (_t.time() - _T0) - 900.0
    _avant = bm.solver.max_runtime_s_per_game
    if _avant and _reste > 0 and _avant > _reste:
        bm.solver.max_runtime_s_per_game = _reste
    _noter("partie", pret=_pret, attente_s=round(_t.time() - _T0, 1), duree_jeu_avant_s=_avant,
           duree_jeu_s=bm.solver.max_runtime_s_per_game)
except Exception as _e:
    _noter("partie", pret=_pret, erreur=repr(_e)[:200])
'''

APRES = r'''# CHRYSALIDE — fin de partie (D, CW-455, étape 5)
try:
    _noter("fin", duree_s=round(_t.time() - _T0, 1))
except Exception:
    pass
'''
