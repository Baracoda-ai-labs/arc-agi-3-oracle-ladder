"""Films comme preuves perceptives ; aucune image intermédiaire ne devient un état de plan."""
import hashlib

import numpy as np

from chrysalide.arc3.films import evenements_types


class Films:
    def __init__(self):
        self.entrees = []
        self.cache = {}
        self.extractions = 0

    def ajouter(self, avant, images):
        if images is None:
            self.entrees.append(None)
            return
        avant = np.asarray(avant, dtype=np.int16).copy()
        images = np.asarray(images, dtype=np.int16).copy()
        if images.ndim != 3 or not len(images) or images.shape[1:] != avant.shape:
            raise ValueError('Film absent, vide ou de forme incompatible')
        sha = hashlib.sha256(avant.tobytes() + images.tobytes() + str(images.shape).encode()).hexdigest()
        self.entrees.append({'avant': avant, 'images': images, 'sha256': sha})

    def signatures(self):
        return [e['sha256'] if e else None for e in self.entrees]

    def analyser(self, indice):
        entree = self.entrees[indice]
        if entree is None:
            return {'statut': 'film_absent'}
        sha = entree['sha256']
        if sha not in self.cache:
            events, preuve = evenements_types(entree['avant'], entree['images'])
            self.extractions += 1
            regions = [e['region'] for e in events if not e['bord']]
            h, w = entree['avant'].shape
            roi = ([max(0, min(r[0] for r in regions) - 2), max(0, min(r[1] for r in regions) - 2),
                    min(w, max(r[2] for r in regions) + 3), min(h, max(r[3] for r in regions) + 3)]
                   if regions else [0, 0, w, h])
            self.cache[sha] = {'statut': 'film_disponible', 'sha256': sha,
                'n_images': len(entree['images']), 'information_temporelle': len(entree['images']) > 1,
                'evenements': events, 'preuve': preuve, 'recadrage_fixe': roi,
                'portee': 'evenements visuels, pas loi causale ni victoire'}
        return self.cache[sha]

    def images_agrandies(self, indice, facteur=10):
        """Vue intégrale de toutes les frames, sans interpolation ni modification des preuves."""
        from PIL import Image
        from chrysalide.qwen.images import PAL
        if facteur not in (4,10):raise ValueError("Zoom attendu x4 ou x10")
        entree=self.entrees[indice]
        if entree is None:return []
        return [Image.fromarray(PAL[g % 16]).resize((g.shape[1]*facteur,g.shape[0]*facteur),Image.Resampling.NEAREST)
                for g in [entree['avant'],*entree['images']]]

    def planches(self, indice, par_page=6):
        """Toutes les images, ordre et repère conservés ; vue globale avant chaque série."""
        from PIL import Image, ImageDraw

        from chrysalide.qwen.images import PAL, _png, _police
        entree = self.entrees[indice]
        if entree is None:
            return []
        info = self.analyser(indice)
        x0, y0, x1, y1 = info['recadrage_fixe']
        frames = [entree['avant'], *entree['images']]
        images = []
        for debut in range(0, len(frames), par_page):
            selection = frames[debut:debut + par_page]
            largeur, haut = 256, 288
            page = Image.new('RGB', (largeur * (len(selection) + 1), haut), 'white')
            d = ImageDraw.Draw(page)
            globale = Image.fromarray(PAL[entree['avant'] % 16]).resize((256, 256), Image.Resampling.NEAREST)
            page.paste(globale, (0, 32))
            d.text((4, 4), 'Repere global AVANT', fill='black', font=_police(12))
            for i, frame in enumerate(selection, 1):
                crop = frame[y0:y1, x0:x1]
                im = Image.fromarray(PAL[crop % 16])
                im.thumbnail((256, 256), Image.Resampling.NEAREST)
                facteur = max(1, min(256 // im.width, 256 // im.height))
                im = im.resize((im.width * facteur, im.height * facteur), Image.Resampling.NEAREST)
                page.paste(im, (i * largeur, 32))
                d.text((i * largeur + 4, 4), f'Image {debut + i - 1} ROI {x0},{y0}',
                       fill='black', font=_police(12))
            images.append(_png(page))
        return images
