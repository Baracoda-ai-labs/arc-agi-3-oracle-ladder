"""Registre SQLite des résultats (une ligne par tâche × passe), en plus des JSONL bruts."""
from pathlib import Path

from sqlmodel import Field, Session, SQLModel, create_engine


class Resultat(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run: str
    passe: str
    modele: str
    mode: str
    pensant: bool
    monde: str
    tache: str
    famille: str
    structure: str
    statut: str
    tokens_prompt: int = 0
    tokens_sortie: int = 0
    mur_s: float = 0.0
    force: bool = False
    tronque: bool = False


class Registre:
    def __init__(self, path, run):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine, self.run = create_engine(f"sqlite:///{Path(path)}"), run
        SQLModel.metadata.create_all(self.engine)

    def __call__(self, p, monde, t, statut, m):
        with Session(self.engine) as s:
            s.add(Resultat(run=self.run, passe=p["name"], modele=p.get("model") or p.get("backend") or "vllm", mode=p["mode"],
                           pensant=bool(p.get("pensant")), monde=Path(monde).stem, tache=t["id"], famille=t["family"],
                           structure=t["structure_id"], statut=statut, tokens_prompt=m.get("tokens_prompt", 0) or 0,
                           tokens_sortie=m.get("tokens_sortie", 0) or 0, mur_s=m.get("mur_s", 0.0),
                           force=bool(m.get("force")), tronque=bool(m.get("tronque"))))
            s.commit()
