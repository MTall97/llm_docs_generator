"""Thèmes visuels : palette, polices, logo, marges, lus dans un fichier TOML."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_THEMES = RACINE / "themes"

# Polices TTF nécessaires au PDF (fpdf2 a besoin d'un fichier pour l'Unicode).
POLICES_SYSTEME = [
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    Path("/Library/Fonts"),
    Path("C:/Windows/Fonts"),
]


@dataclass
class Theme:
    nom: str = "sobre"
    primaire: str = "#1F4E79"
    secondaire: str = "#2E86AB"
    accent: str = "#F18F01"
    texte: str = "#222222"
    fond: str = "#FFFFFF"
    palette_graphiques: list[str] = field(default_factory=lambda: [
        "#1F4E79", "#F18F01", "#2E86AB", "#C73E1D", "#3B8E3B", "#7D5BA6"])
    police_titre: str = "DejaVuSans-Bold.ttf"
    police_texte: str = "DejaVuSans.ttf"
    police_pptx: str = "Calibri"
    logo: str | None = None
    marge_mm: float = 18.0
    taille_texte: float = 11.0
    modele_pptx: str | None = None   # modèle PowerPoint fourni par l'utilisateur

    def rgb(self, cle: str) -> tuple[int, int, int]:
        h = getattr(self, cle).lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def chemin_police(self, nom: str) -> Path | None:
        p = Path(nom)
        if p.is_file():
            return p
        for d in POLICES_SYSTEME:
            if (d / nom).is_file():
                return d / nom
        return None


def charger_theme(nom_ou_chemin: str | None = None) -> Theme:
    if not nom_ou_chemin:
        return Theme()
    p = Path(nom_ou_chemin)
    if not p.is_file():
        p = DOSSIER_THEMES / f"{nom_ou_chemin}.toml"
    with open(p, "rb") as f:
        d = tomllib.load(f)
    plat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            plat.update(v)
        else:
            plat[k] = v
    for cle in ("logo", "modele_pptx"):  # chemins relatifs au fichier du thème
        if plat.get(cle) and not Path(plat[cle]).is_absolute():
            plat[cle] = str((p.parent / plat[cle]).resolve())
    connus = Theme.__dataclass_fields__
    return Theme(**{k: v for k, v in plat.items() if k in connus})
