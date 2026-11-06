import io

import numpy as np
from PIL import Image

from chrysalide.qwen.images import images_coup


def test_images_coup():
    a = np.zeros((64, 64), int)
    b = a.copy()
    b[10:14, 10:14] = 9
    brute, annotee = images_coup(a, b, predit=a, scene=[{"id": "o1", "boite": (10, 10, 4, 4)}])
    ib, ia = Image.open(io.BytesIO(brute)), Image.open(io.BytesIO(annotee))
    assert ib.size == (2 * 640 + 16, 640)
    assert ia.size[0] > ib.size[0] and ia.size[1] > 640
    px = np.asarray(ia.convert("RGB"))
    assert ((px == (230, 0, 0)).all(-1)).any()  # zone fausse entourée en rouge
