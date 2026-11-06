import json
from concurrent.futures import ThreadPoolExecutor
import time
from session_sdk_observee import demander

def test_reponse_partielle_attendue_sans_reemettre_commande(tmp_path):
    def repondre():
        limite=time.monotonic()+2
        while not list(tmp_path.glob('commande_*.json')):
            assert time.monotonic()<limite
            time.sleep(.005)
        p=next(tmp_path.glob('commande_*.json')).with_suffix('.resultat.json')
        p.write_text('{')
        time.sleep(.1)
        p.write_text(json.dumps({'ok':True}))
    with ThreadPoolExecutor(max_workers=1) as pool:
        futur=pool.submit(repondre)
        assert demander(tmp_path,{'op':'play','action':1},timeout=2)=={'ok':True}
        futur.result()
    assert len(list(tmp_path.glob('commande_*.json')))==2
