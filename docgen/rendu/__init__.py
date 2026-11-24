"""Moteurs de rendu déterministes : JSON du schéma → fichiers."""
from __future__ import annotations

from pathlib import Path

from ..schema import valider
from ..theme import Theme
from .markdown import rendre_markdown
from .pdf import rendre_pdf
from .pptx import rendre_pptx
from .xlsx import rendre_xlsx

MOTEURS = {"md": rendre_markdown, "pdf": rendre_pdf, "pptx": rendre_pptx, "xlsx": rendre_xlsx}
# Formats proposés par défaut pour chaque sorte de livrable.
FORMATS_PAR_DEFAUT = {"document": ["md", "pdf"], "presentation": ["pptx", "pdf"], "classeur": ["xlsx", "md"]}


def rendre(d: dict, sortie: str | Path, formats=None, theme: Theme | None = None,
           base: Path | None = None, verifier=True) -> list[Path]:
    """Écrit `sortie`.<format> pour chaque format. `base` : dossier des images de l'utilisateur."""
    if verifier:
        # Seules les erreurs de structure bloquent ; les incohérences (ligne trop
        # courte…) sont réparées par nettoyage.nettoyer() ou tolérées au rendu.
        erreurs = [e for e in valider(d) if " : " in e and not e.split(" : ")[1].startswith(("la série", "colonne inconnue"))
                   and "cellules pour" not in e]
        if erreurs:
            raise ValueError("JSON non conforme au schéma :\n- " + "\n- ".join(erreurs[:10]))
    sortie = Path(sortie)
    formats = formats or FORMATS_PAR_DEFAUT[d["type"]]
    return [MOTEURS[f](d, sortie.with_suffix("." + f), theme, base) for f in formats]
