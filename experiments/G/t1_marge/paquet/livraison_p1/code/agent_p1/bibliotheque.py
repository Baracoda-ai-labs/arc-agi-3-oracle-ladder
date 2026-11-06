"""Bibliothèque de mécanismes validés (fichier JSON, versionné, jamais écrasé sans trace).

Critères de promotion (avis expert, « nouvelle famille ») :
 1. nouveaute : le programme utilise au moins un opérateur absent de la bibliothèque initiale ;
 2. prediction : >= N_PRED transitions prédites correctement APRÈS l'invention (données non utilisées pour l'inventer) ;
 3. intervention : au moins une expérience jouée a départagé l'hypothèse de sa plus forte concurrente ;
 4. reutilisation : statut 'transfere' seulement après usage réussi dans un niveau distinct.
Un mécanisme en bibliothèque est un gabarit : les champs d'instance (route, positions) sont retirés.
"""
import json, time
from pathlib import Path

N_PRED = 5
CHAMPS_INSTANCE = ('route',)


def gabarit(prog):
    return {k: (None if k in CHAMPS_INSTANCE else v) for k, v in prog.items()}


class Bibliotheque:
    def __init__(self, path):
        self.path = Path(path)
        self.d = json.loads(self.path.read_text()) if self.path.exists() else dict(version=0, mecanismes=[], historique=[])

    def mecanismes(self, statut_min='candidat'):
        ordre = {'candidat': 0, 'valide': 1, 'transfere': 2}
        return [m for m in self.d['mecanismes'] if ordre[m['statut']] >= ordre[statut_min]]

    def proposer(self, prog, preuves, source):
        """preuves : dict(nouveaute=[...], n_pred_prospectives=int, interventions=[...])."""
        ok = bool(preuves['nouveaute']) and preuves['n_pred_prospectives'] >= N_PRED and preuves['interventions']
        g = gabarit(prog)
        for m in self.d['mecanismes']:
            if m['programme'] == g:
                m['sources'].append(source); m['preuves'].append(preuves)
                if ok and m['statut'] == 'candidat':
                    m['statut'] = 'valide'
                self._sauver('maj'); return m
        m = dict(id=f"MEC{len(self.d['mecanismes']) + 1:03d}", programme=g, statut='valide' if ok else 'candidat',
                 sources=[source], preuves=[preuves], date=time.strftime('%Y-%m-%dT%H:%M:%S'))
        self.d['mecanismes'].append(m); self._sauver('ajout'); return m

    def marquer_transfert(self, mid, source, succes, detail):
        for m in self.d['mecanismes']:
            if m['id'] == mid:
                distinct = not any(src.startswith(source + '_') or src == source for src in m['sources'])
                m.setdefault('transferts', []).append(dict(source=source, succes=succes, detail=detail,
                                                           niveau_distinct=distinct))
                if succes and distinct and m['statut'] == 'valide':   # critère 4 : niveau distinct seulement
                    m['statut'] = 'transfere'
        self._sauver('transfert')

    def _sauver(self, quoi):
        self.d['version'] += 1
        self.d['historique'].append(dict(version=self.d['version'], quoi=quoi, date=time.strftime('%H:%M:%S')))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.d, indent=1, default=str, ensure_ascii=False))
