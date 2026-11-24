"""JSON → Markdown. Les images sont écrites dans un dossier voisin."""
from __future__ import annotations

from pathlib import Path

from ..theme import Theme
from .images import produire_image


def _cellule(v) -> str:
    return str(v if v is not None else "").replace("|", "\\|").replace("\n", " ")


def _tableau(entetes, lignes) -> list[str]:
    n = len(entetes)
    out = ["| " + " | ".join(_cellule(e) for e in entetes) + " |", "|" + "---|" * n]
    for l in lignes:
        l = (list(l) + [""] * n)[:n]
        out.append("| " + " | ".join(_cellule(c) for c in l) + " |")
    return out


def _image(bloc, sortie: Path, theme, base) -> list[str]:
    if bloc["type"] == "schema" and bloc.get("langage") == "mermaid" and "code" in bloc:
        # GitHub, GitLab, Obsidian… affichent Mermaid nativement.
        out = ["```mermaid", bloc["code"].strip(), "```"]
        return out + (["", f"*{bloc['legende']}*"] if bloc.get("legende") else [])
    dossier = sortie.parent / f"{sortie.stem}_images"
    chemin, msg = produire_image(bloc, dossier, theme, base)
    legende = bloc.get("legende") or bloc.get("titre") or bloc.get("mot_cle", "")
    if not chemin:
        return [f"> ⚠️ {msg}"]
    if chemin.parent != dossier:  # image de l'utilisateur : on la copie à côté
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / chemin.name).write_bytes(chemin.read_bytes())
        chemin = dossier / chemin.name
    rel = chemin.relative_to(sortie.parent).as_posix()
    largeur = ' width="64"' if bloc["type"] == "icone" else ""
    if largeur:
        return [f'<img src="{rel}" alt="{legende}"{largeur}>']
    return [f"![{legende}]({rel})"] + (["", f"*{bloc['legende']}*"] if bloc.get("legende") else [])


def bloc_vers_md(b: dict, sortie: Path, theme: Theme, base) -> list[str]:
    t = b["type"]
    if t == "paragraphe":
        return [b["texte"]]
    if t == "liste":
        return [(f"{i}. " if b.get("ordonnee") else "- ") + e for i, e in enumerate(b["elements"], 1)]
    if t == "tableau":
        return _tableau(b["entetes"], b["lignes"]) + (["", f"*{b['legende']}*"] if b.get("legende") else [])
    if t == "citation":
        return [f"> {b['texte']}"] + ([f">", f"> — {b['auteur']}"] if b.get("auteur") else [])
    return _image(b, sortie, theme, base)


def rendre_markdown(d: dict, sortie: Path, theme: Theme | None = None, base: Path | None = None) -> Path:
    theme = theme or Theme()
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    md = [f"# {d['titre']}"]
    if d.get("sous_titre"):
        md += ["", f"*{d['sous_titre']}*"]
    if d["type"] == "document":
        for s in d["sections"]:
            md += ["", f"## {s['titre']}"]
            for b in s["blocs"]:
                md += [""] + bloc_vers_md(b, sortie, theme, base)
    elif d["type"] == "presentation":
        for i, dia in enumerate(d["diapositives"], 1):
            md += ["", "---", ""] + _diapo_md(dia, i, sortie, theme, base)
    elif d["type"] == "classeur":
        from .xlsx import valeurs_calculees
        for f in d["feuilles"]:
            entetes, lignes = valeurs_calculees(f)
            md += ["", f"## {f['nom']}", ""] + _tableau(entetes, lignes)
    sortie.write_text("\n".join(md).rstrip() + "\n", encoding="utf-8")
    return sortie


def _diapo_md(dia, i, sortie, theme, base) -> list[str]:
    m = dia["mise_en_page"]
    titre = dia.get("titre") or ("Citation" if m == "citation" else f"Diapositive {i}")
    out = [f"## {i}. {titre}", ""]
    if m == "titre":
        out += [f"*{dia.get('sous_titre', '')}*"]
    elif m == "points":
        out += [f"- {p}" for p in dia["points"]]
    elif m == "deux_colonnes":
        for c in (dia["gauche"], dia["droite"]):
            out += [f"**{c['titre']}**", ""] + [f"- {p}" for p in c["points"]] + [""]
    elif m == "image_texte":
        out += _image(dia["image"], sortie, theme, base) + [""] + [f"- {p}" for p in dia["points"]]
    elif m == "chiffre_cle":
        out += [f"# **{dia['chiffre']}**", "", dia["legende"]]
    elif m == "citation":
        out += [f"> {dia['texte']}"] + ([f"> — {dia['auteur']}"] if dia.get("auteur") else [])
    if dia.get("notes"):
        out += ["", f"<!-- notes : {dia['notes']} -->"]
    return out
