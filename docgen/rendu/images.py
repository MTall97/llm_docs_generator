"""Transforme un bloc image du schéma en fichier PNG.

Aucune IA ici : matplotlib pour les graphiques, Graphviz `dot` pour les
schémas, une bibliothèque d'icônes embarquée (Tabler Icons, MIT) pour les
icônes. Si un rendu échoue (code Graphviz invalide écrit par le modèle,
icône inconnue…), on renvoie None et un message : le document est produit
quand même, avec le message à la place de l'image.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

from ..theme import Theme

DOSSIER_ICONES = Path(__file__).resolve().parent.parent / "icones"


def _cle(bloc: dict) -> str:
    return hashlib.sha1(json.dumps(bloc, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def produire_image(bloc: dict, dossier: Path, theme: Theme, base: Path | None = None) -> tuple[Path | None, str]:
    """Renvoie (chemin_png, message). chemin_png vaut None en cas d'échec."""
    dossier.mkdir(parents=True, exist_ok=True)
    sorte = bloc.get("type")
    try:
        if sorte == "graphique":
            return dessiner_graphique(bloc, dossier / f"graphique_{_cle(bloc)}.png", theme), ""
        if sorte == "schema":
            return dessiner_schema(bloc, dossier / f"schema_{_cle(bloc)}.png", theme)
        if sorte == "icone":
            return dessiner_icone(bloc["mot_cle"], dossier / f"icone_{_cle(bloc)}.png", theme)
        if sorte == "image":
            p = Path(bloc["chemin"])
            if not p.is_absolute() and base is not None:
                p = base / p
            return (p, "") if p.is_file() else (None, f"image introuvable : {bloc['chemin']}")
    except Exception as e:  # le rendu ne doit jamais bloquer le document
        return None, f"{sorte} non rendu : {type(e).__name__}: {e}"[:300]
    return None, f"bloc image inconnu : {sorte}"


# --- Graphiques -------------------------------------------------------------------
def dessiner_graphique(g: dict, sortie: Path, theme: Theme) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    etiquettes = [str(e) for e in g["etiquettes"]]
    n = len(etiquettes)
    couleurs = theme.palette_graphiques
    fig, ax = plt.subplots(figsize=(7, 4), dpi=150)
    series = [(s["nom"], (list(s["valeurs"]) + [0] * n)[:n]) for s in g["series"]]
    if g["forme"] == "camembert":
        nom, vals = series[0]
        vals = [max(0, v) for v in vals]
        ax.pie(vals, labels=etiquettes, colors=couleurs[:n] if n <= len(couleurs) else None,
               autopct="%1.0f %%", startangle=90, counterclock=False,
               wedgeprops={"linewidth": 2, "edgecolor": "white"})
        ax.axis("equal")
    else:
        x = range(n)
        largeur = 0.8 / max(1, len(series))
        for i, (nom, vals) in enumerate(series):
            c = couleurs[i % len(couleurs)]
            if g["forme"] == "barres":
                ax.bar([xi + (i - (len(series) - 1) / 2) * largeur for xi in x], vals, largeur, label=nom, color=c)
            else:
                ax.plot(list(x), vals, marker="o", linewidth=2, label=nom, color=c)
        ax.set_xticks(list(x), etiquettes, rotation=0 if n <= 6 else 30, ha="center" if n <= 6 else "right")
        for cote in ("top", "right"):
            ax.spines[cote].set_visible(False)
        ax.grid(axis="y", alpha=0.3)
        if len(series) > 1:
            ax.legend(frameon=False)
    ax.set_title(g.get("titre", ""), color=theme.texte, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(sortie)
    plt.close(fig)
    return sortie


# --- Schémas (Graphviz ; Mermaid converti) ------------------------------------------
_FLECHE = re.compile(r"\s*(-->|---|-\.->|==>)\s*(?:\|([^|]*)\|\s*)?")
_NOEUD = re.compile(r"^\s*([A-Za-z0-9_]+)\s*(?:\[\(?\"?([^\]\)\"]*)\"?\)?\]|\(\(?\"?([^)\"]*)\"?\)?\)|\{\"?([^}\"]*)\"?\})?\s*$")


def mermaid_vers_dot(code: str) -> str:
    """Convertit le sous-ensemble « flowchart » de Mermaid en DOT.

    On ne dépend pas de mermaid-cli (Node + Chromium) : les petits modèles
    écrivent surtout des organigrammes simples (A[Texte] --> B[Texte])."""
    lignes = [l.strip() for l in re.split(r"[\n;]", code) if l.strip()]
    sens = "TB"
    if lignes and re.match(r"^(graph|flowchart)\b", lignes[0]):
        m = re.search(r"\b(TD|TB|LR|RL|BT)\b", lignes[0])
        sens = {"TD": "TB"}.get(m.group(1), m.group(1)) if m else "TB"
        lignes = lignes[1:]
    noeuds, aretes = {}, []

    def lire(fragment):
        m = _NOEUD.match(fragment)
        if not m:
            ident = re.sub(r"\W+", "_", fragment.strip()) or "n"
            noeuds.setdefault(ident, fragment.strip())
            return ident
        ident = m.group(1)
        texte = m.group(2) or m.group(3) or m.group(4)
        if texte or ident not in noeuds:
            noeuds[ident] = texte or noeuds.get(ident, ident)
        return ident

    for l in lignes:
        if l.startswith(("%%", "style", "classDef", "class ", "subgraph", "end", "click")):
            continue
        morceaux = _FLECHE.split(l)
        # split avec groupes : [noeud, fleche, etiquette, noeud, fleche, etiquette, noeud...]
        if len(morceaux) == 1:
            lire(morceaux[0])
            continue
        prec = lire(morceaux[0])
        for k in range(1, len(morceaux) - 2, 3):
            suiv = lire(morceaux[k + 2])
            aretes.append((prec, suiv, (morceaux[k + 1] or "").strip()))
            prec = suiv
    if not noeuds:
        raise ValueError("aucun nœud reconnu dans le code Mermaid")
    out = [f"digraph G {{ rankdir={sens};"]
    for i, t in noeuds.items():
        out.append(f'  "{i}" [label="{t.replace(chr(34), chr(39))}"];')
    for a, b, e in aretes:
        out.append(f'  "{a}" -> "{b}"' + (f' [label="{e}"]' if e else "") + ";")
    out.append("}")
    return "\n".join(out)


def _habiller_dot(code: str, theme: Theme) -> str:
    """Ajoute le style du thème et répare les oublis fréquents des petits modèles."""
    code = code.strip().strip("`")
    if code.startswith("dot\n"):
        code = code[4:]
    if not re.match(r"^\s*(strict\s+)?(di)?graph\b", code):
        code = "digraph G {\n" + code + "\n}"
    style = (f'graph [fontname="DejaVu Sans", bgcolor="white", pad=0.3]; '
             f'node [shape=box, style="rounded,filled", fillcolor="{theme.fond}", color="{theme.primaire}", '
             f'fontname="DejaVu Sans", fontcolor="{theme.texte}", penwidth=1.5]; '
             f'edge [color="{theme.secondaire}", fontname="DejaVu Sans", fontsize=10];')
    return code.replace("{", "{ " + style, 1)


def liens_vers_dot(bloc: dict) -> str:
    """Variante structurée {liens: [{de, vers, etiquette}]} → DOT."""
    q = lambda t: '"' + str(t).replace('"', "'") + '"'
    sens = "LR" if bloc.get("sens") == "gauche-droite" else "TB"
    lignes = [f"digraph G {{ rankdir={sens};"]
    vus = set()
    for l in bloc["liens"]:
        cle = (l["de"], l["vers"], l.get("etiquette", ""))
        if cle in vus:  # arêtes répétées : fréquent chez les petits modèles
            continue
        vus.add(cle)
        lignes.append(f"  {q(l['de'])} -> {q(l['vers'])}" + (f" [label={q(l['etiquette'])}]" if l.get("etiquette") else "") + ";")
    return "\n".join(lignes + ["}"])


def dessiner_schema(bloc: dict, sortie: Path, theme: Theme) -> tuple[Path | None, str]:
    if not shutil.which("dot"):
        return None, "Graphviz (dot) n'est pas installé : schéma non rendu"
    code = liens_vers_dot(bloc) if "liens" in bloc else bloc["code"]
    if bloc.get("langage") == "mermaid":
        code = mermaid_vers_dot(code)
    dot = _habiller_dot(code, theme)
    r = subprocess.run(["dot", "-Tpng", "-Gdpi=150", "-o", str(sortie)], input=dot.encode(),
                       capture_output=True, timeout=30)
    if r.returncode != 0 or not sortie.exists():
        return None, "code de schéma invalide : " + r.stderr.decode(errors="replace")[:200]
    return sortie, ""


# --- Icônes -------------------------------------------------------------------------
def _sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def trouver_icone(mot_cle: str) -> str | None:
    index = json.loads((DOSSIER_ICONES / "index.json").read_text(encoding="utf-8"))
    mots = set(re.findall(r"\w+", _sans_accents(mot_cle)))
    meilleur, score = None, 0
    for nom, cles in index.items():
        cles_n = {_sans_accents(c) for c in cles} | set(nom.split("-"))
        s = len(mots & cles_n)
        # correspondance partielle : « financier » ~ « finances »
        s += 0.5 * sum(1 for m in mots for c in cles_n if len(m) > 4 and m[:5] == c[:5] and m != c)
        if s > score:
            meilleur, score = nom, s
    return meilleur


def dessiner_icone(mot_cle: str, sortie: Path, theme: Theme) -> tuple[Path | None, str]:
    nom = trouver_icone(mot_cle)
    if not nom:
        return None, f"aucune icône pour « {mot_cle} »"
    svg = (DOSSIER_ICONES / f"{nom}.svg").read_text(encoding="utf-8").replace("currentColor", theme.primaire)
    try:
        import cairosvg
    except ImportError:
        return None, "cairosvg absent : icône non rendue"
    cairosvg.svg2png(bytestring=svg.encode(), write_to=str(sortie), output_width=256, output_height=256)
    return sortie, ""
