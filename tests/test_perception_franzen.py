import base64
import io
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from chrysalide.arc3 import perception_franzen as pf

RACINE = Path(__file__).resolve().parents[1]
FRANZEN = RACINE / "tiers/arc-agi-3-solution/ARC3-Inference"


@dataclass
class Frame:
    grid: tuple
    step: int
    level: int


def png(grille, k):
    im = Image.new("RGB", (len(grille[0]), len(grille)))
    for r, rang in enumerate(grille):
        for c, v in enumerate(rang):
            im.putpixel((c, r), (v * 15, 255 - v * 15, (v * 40) % 256))
    im = im.resize((im.width * k, im.height * k), Image.Resampling.NEAREST)
    b = io.BytesIO()
    im.save(b, format="PNG")
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()}}


def pixels(part):
    im = Image.open(io.BytesIO(base64.b64decode(part["image_url"]["url"].split(",", 1)[1]))).convert("RGB")
    return im.size, im.tobytes()


class Agent:
    def __init__(self):
        self._pending_gameover_images, self._pending_diff_image, self._pending_animation_image = [], None, None


GRILLE = tuple(tuple((r * 7 + c * 3) % 16 for c in range(64)) for r in range(64))


def test_reduction_10_vers_4_exacte_case_par_case():
    assert pixels(pf.reduire_part(png(GRILLE, 10), 10, 4)) == pixels(png(GRILLE, 4))


def test_eteint_rend_exactement_franzen_sans_fichier(monkeypatch, tmp_path):
    monkeypatch.delenv("CHRYS_PERCEPTION", raising=False)
    monkeypatch.setenv("CHRYS_DOSSIER", str(tmp_path / "runs"))
    a, f = Agent(), Frame(GRILLE, 0, 1)
    ref = png(GRILLE, 10)
    assert pf.image_tour(a, f, lambda fr: ref) is ref
    assert not hasattr(a, "_chrys_perc") and not (tmp_path / "runs").exists()


def test_allume_haute_puis_compacte_reduit_aussi_le_diff(monkeypatch, tmp_path):
    monkeypatch.setenv("CHRYS_PERCEPTION", "1")
    monkeypatch.setenv("MULTIMODAL_UPSCALE", "10")
    monkeypatch.setenv("CHRYS_DOSSIER", str(tmp_path))
    a, defaut = Agent(), (lambda fr: png(fr.grid, 10))
    tailles = []
    for i in range(4):
        g = tuple(tuple((v + i) % 16 for v in rang) for rang in GRILLE)  # état neuf à chaque tour
        a._pending_diff_image = png(GRILLE, 10)
        tailles.append((pixels(pf.image_tour(a, Frame(g, i, 1), defaut))[0], pixels(a._pending_diff_image)[0]))
    assert tailles[0] == tailles[1] == ((640, 640), (640, 640))
    assert tailles[2] == tailles[3] == ((256, 256), (256, 256))
    a._pending_gameover_images = [("mort", None)]
    assert pixels(pf.image_tour(a, Frame(GRILLE, 9, 1), defaut))[0] == (640, 640)
    assert len((tmp_path / "perception.jsonl").read_text().splitlines()) == 5


def test_patcher_ancre_unique_et_idempotent(tmp_path):
    from scripts.arc3.patcher_perception import ANCRE, MARQUE, patcher
    src = FRANZEN / "inference/agent/tool_agent.py"
    assert src.read_text().count(ANCRE) == 1
    copie = tmp_path / "ARC3-Inference"
    (copie / "inference/agent").mkdir(parents=True)
    shutil.copy(src, copie / "inference/agent/tool_agent.py")
    assert patcher(copie) == "patché"
    assert patcher(copie) == "déjà patché"
    assert (copie / "inference/agent/tool_agent.py").read_text().count(MARQUE) == 1
    t = (copie / "inference/chrysalide_arc3/perception_franzen.py").read_text()
    assert "from chrysalide.arc3." not in t
