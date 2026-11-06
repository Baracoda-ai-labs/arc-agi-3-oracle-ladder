"""Règles de rendu des faces observées au contact, sans loi de déplacement."""
import numpy as np


def regles_faces(coque, faces, pieces, actif, voisins=None):
    if not faces:
        return []
    voisins = pieces if voisins is None else voisins
    regles = [{"nom":"coque_hors_contact", "phase":-1, "quand":True,
        "alors":[["pour","$o",pieces,
            [["ecrire","$o",int(y),int(x),int(coque[y,x])]
             for y,x in np.argwhere(coque >= 0)]]]}]
    for dx,dy,face,couleur in faces:
        adjacent = ["existe","$p",voisins,["et",["!=","$o","$p"],
            ["=",["x","$p"],["+",["x","$o"],dx]],
            ["=",["y","$p"],["+",["y","$o"],dy]]]]
        regles.append({"nom":f"face_contact_{dx}_{dy}","phase":1,"quand":True,
            "alors":[["pour","$o",pieces,[["si_alors",["et",actif,adjacent],
                [["ecrire","$o",iy,ix,couleur] for iy,ix in face],[]]]]]})
    return regles
