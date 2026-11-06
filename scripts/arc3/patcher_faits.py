# SPDX-License-Identifier: MIT-0 AND Apache-2.0
"""Applique le pont à une COPIE explicite du harnais Franzen ; zéro SDK.

Refuse une version inattendue avant toute écriture dans le fichier cible.
Ne modifie ni le paquet de référence ni une soumission.
"""
from pathlib import Path
import sys

HIST='        current_frame, history_entries = load_runtime_state(state_path)\n'
PROMPT='        user_prompt += self._retained_function_context()\n'
TAG='# CHRYSALIDE-FAITS-VISUELS'
HIST_PATCH=HIST+f"        if os.environ.get('CHRYS_FAITS', '0') == '1':  {TAG}\n            self._chrys_faits_history = history_entries\n"
PROMPT_PATCH=PROMPT+f"        if os.environ.get('CHRYS_FAITS', '0') == '1':  {TAG}\n            try:\n                from inference.chrysalide_arc3.faits_bridge import contexte as _chrys_faits\n                user_prompt += _chrys_faits(getattr(self, '_chrys_faits_history', ()), current_frame)\n            except Exception:\n                pass\n"

def transformer(source):
 if TAG in source:return source
 if source.count(HIST)!=2 or source.count(PROMPT)!=1:raise ValueError('ancres Franzen absentes ou ambiguës')
 result=source.replace(HIST,HIST_PATCH).replace(PROMPT,PROMPT_PATCH)
 compile(result,'tool_agent.py','exec')
 return result

def patcher(dossier):
 root=Path(dossier); agent=root/'inference/agent/tool_agent.py';s=agent.read_text(); t=transformer(s)
 paquet=root/'inference/chrysalide_arc3';paquet.mkdir(parents=True,exist_ok=True)
 init=paquet/'__init__.py'
 if not init.exists():init.write_text('')
 for nom in ('faits_franzen.py','faits_bridge.py'):(paquet/nom).write_bytes(Path(__file__).with_name(nom).read_bytes())
 if t!=s:agent.write_text(t)
 return 'déjà patché' if t==s else 'patché'
if __name__=='__main__':
 if len(sys.argv)!=2:raise SystemExit('un dossier COPIE du harnais est requis')
 print(patcher(sys.argv[1]))
