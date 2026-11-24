"""JSON → Excel (openpyxl), avec de vraies formules.

Le modèle écrit les formules avec des noms de colonnes : « {Prix} * {Quantité} ».
Le moteur les traduit ligne par ligne en références A1 (=C2*D2) et ajoute les
totaux (=SUM(C2:C9)). Le classeur reste donc juste si l'utilisateur modifie
une valeur, et aucun calcul n'est confié au modèle.
"""
from __future__ import annotations

import ast
import operator
import re
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from ..theme import Theme

FONCTIONS = {"SOMME": "SUM", "MOYENNE": "AVERAGE", "MIN": "MIN", "MAX": "MAX", "NB": "COUNT"}
FORMATS = {"nombre": "#,##0.##", "monnaie": '#,##0.00## "€"', "pourcentage": "0.0%", "date": "DD/MM/YYYY"}
_REF = re.compile(r"\{([^{}]+)\}|\[([^\[\]]+)\]")


def document_vers_classeur(d: dict) -> dict:
    """Chaque tableau d'un document devient une feuille."""
    feuilles = []
    for s in d["sections"]:
        for b in s["blocs"]:
            if b["type"] == "tableau":
                nom = re.sub(r"[\[\]\*\?/\\:]", " ", b.get("legende") or s["titre"])[:31]
                feuilles.append({"nom": nom or f"Tableau {len(feuilles) + 1}",
                                 "colonnes": [{"nom": e, "format": "texte"} for e in b["entetes"]],
                                 "lignes": b["lignes"]})
    if not feuilles:
        raise ValueError("ce document ne contient aucun tableau à mettre dans un classeur")
    return {"type": "classeur", "titre": d["titre"], "feuilles": feuilles}


# --- Valeurs ---------------------------------------------------------------------
def nombre(v):
    """« 1 200,50 € » → 1200.5 ; renvoie None si ce n'est pas un nombre."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = re.sub(r"[\s  €$%]", "", str(v)).replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "", s.count(".") - 1)
    try:
        f = float(s)
        return int(f) if f.is_integer() and "." not in s else f
    except ValueError:
        return None


def _date(v):
    if isinstance(v, (date, datetime)):
        return v
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            pass
    return v


def _convertir(v, fmt):
    if v is None or v == "":
        return None
    if fmt in ("nombre", "monnaie", "pourcentage"):
        n = nombre(v)
        if n is None:
            return v
        if fmt == "pourcentage" and (abs(n) > 1 or "%" in str(v)):
            n = n / 100  # le modèle écrit « 12 » ou « 12 % » pour 12 %
        return n
    if fmt == "date":
        return _date(v)
    return v


def _lignes_normalisees(f):
    n = len(f["colonnes"])
    calc = [bool(c.get("formule")) for c in f["colonnes"]]
    out = []
    for l in f["lignes"]:
        l = (list(l) + [None] * n)[:n]
        out.append([None if calc[j] else _convertir(v, f["colonnes"][j]["format"]) for j, v in enumerate(l)])
    return out


def _index_colonnes(f):
    return {c["nom"].strip().lower(): j for j, c in enumerate(f["colonnes"])}


def traduire_formule(formule: str, f: dict, ligne_excel: int) -> str:
    """« {Prix} * {Quantité} » → « =C2*D2 ». Lève ValueError si une colonne est inconnue."""
    idx = _index_colonnes(f)

    def rempl(m):
        nom = (m.group(1) or m.group(2)).strip().lower()
        if nom not in idx:
            raise ValueError(f"colonne inconnue dans la formule : {nom!r}")
        return f"{get_column_letter(idx[nom] + 1)}{ligne_excel}"

    corps = _REF.sub(rempl, formule.strip().lstrip("="))
    for fr, en in FONCTIONS.items():
        corps = re.sub(rf"\b{fr}\(", f"{en}(", corps)
    return "=" + corps.replace(";", ",")


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Pow: operator.pow}


def _eval(noeud):
    if isinstance(noeud, ast.Expression):
        return _eval(noeud.body)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)):
        return noeud.value
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_eval(noeud.left), _eval(noeud.right))
    if isinstance(noeud, ast.UnaryOp) and type(noeud.op) in _OPS:
        return _OPS[type(noeud.op)](_eval(noeud.operand))
    raise ValueError("expression non arithmétique")


def evaluer_formule(formule: str, f: dict, ligne: list):
    """Calcule la formule en Python (pour l'aperçu Markdown/PDF). None si impossible."""
    idx = _index_colonnes(f)

    def rempl(m):
        v = nombre(ligne[idx[(m.group(1) or m.group(2)).strip().lower()]])
        if v is None:
            raise ValueError
        return repr(v)

    try:
        expr = _REF.sub(rempl, formule.strip().lstrip("="))
        return _eval(ast.parse(expr, mode="eval"))
    except (ValueError, KeyError, SyntaxError, ZeroDivisionError, TypeError):
        return None


def valeurs_calculees(f: dict) -> tuple[list, list]:
    """En-têtes et lignes avec formules et totaux calculés (aperçu hors Excel)."""
    lignes = _lignes_normalisees(f)
    for l in lignes:
        for j, c in enumerate(f["colonnes"]):
            if c.get("formule"):
                l[j] = evaluer_formule(c["formule"], f, l)
    affichees = [[_afficher(v, c["format"]) for v, c in zip(l, f["colonnes"])] for l in lignes]
    if f.get("totaux"):
        idx = _index_colonnes(f)
        tot = [""] * len(f["colonnes"])
        tot[0] = "Total"
        for t in f["totaux"]:
            j = idx.get(t["colonne"].strip().lower())
            if j is None:
                continue
            vals = [nombre(l[j]) for l in lignes if nombre(l[j]) is not None]
            fn = {"SOMME": sum, "MOYENNE": lambda v: sum(v) / len(v) if v else None,
                  "MIN": lambda v: min(v) if v else None, "MAX": lambda v: max(v) if v else None,
                  "NB": len}[t["fonction"]]
            tot[j] = _afficher(fn(vals), f["colonnes"][j]["format"])
        affichees.append(tot)
    return [c["nom"] for c in f["colonnes"]], affichees


def _afficher(v, fmt):
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if fmt == "pourcentage":
            return f"{v * 100:.1f} %".replace(".", ",")
        if float(v).is_integer() and fmt != "monnaie":
            s = f"{int(v):,}"
        else:  # assez de décimales pour les petits montants (0,004 €)
            dec = 2 if abs(v) >= 0.01 or v == 0 else 4
            s = f"{v:,.{dec}f}"
        s = s.replace(",", " ").replace(".", ",")
        return s + (" €" if fmt == "monnaie" else "")
    return str(v)


# --- Rendu ----------------------------------------------------------------------
def rendre_xlsx(d: dict, sortie: Path, theme: Theme | None = None, base: Path | None = None) -> Path:
    theme = theme or Theme()
    if d["type"] == "document":
        d = document_vers_classeur(d)
    elif d["type"] != "classeur":
        raise ValueError("Excel : seuls les classeurs et les tableaux d'un document sont pris en charge")
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = d["titre"]
    tete = PatternFill("solid", fgColor=theme.primaire.lstrip("#"))
    zebre = PatternFill("solid", fgColor="F3F6FA")
    bord = Border(bottom=Side(style="thin", color="D0D7DE"))
    noms_vus = set()
    for f in d["feuilles"]:
        nom = re.sub(r"[\[\]\*\?/\\:]", " ", f["nom"]).strip()[:31] or "Feuille"
        while nom in noms_vus:
            nom = nom[:28] + f" {len(noms_vus)}"
        noms_vus.add(nom)
        ws = wb.create_sheet(nom)
        cols = f["colonnes"]
        for j, c in enumerate(cols, 1):
            cel = ws.cell(1, j, c["nom"])
            cel.font, cel.fill = Font(bold=True, color="FFFFFF"), tete
            cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        lignes = _lignes_normalisees(f)
        for i, l in enumerate(lignes, 2):
            for j, (v, c) in enumerate(zip(l, cols), 1):
                if c.get("formule"):
                    try:
                        v = traduire_formule(c["formule"], f, i)
                    except ValueError as e:
                        v = f"⚠ {e}"
                cel = ws.cell(i, j, v)
                if c["format"] in FORMATS:
                    cel.number_format = FORMATS[c["format"]]
                cel.border = bord
                if i % 2 == 1:
                    cel.fill = zebre
        der = len(lignes) + 1
        if f.get("totaux"):
            idx = _index_colonnes(f)
            ws.cell(der + 1, 1, "Total").font = Font(bold=True)
            for t in f["totaux"]:
                j = idx.get(t["colonne"].strip().lower())
                if j is None:
                    continue
                L = get_column_letter(j + 1)
                cel = ws.cell(der + 1, j + 1, f"={FONCTIONS[t['fonction']]}({L}2:{L}{der})")
                cel.font = Font(bold=True)
                if cols[j]["format"] in FORMATS:
                    cel.number_format = FORMATS[cols[j]["format"]]
        for j, c in enumerate(cols, 1):  # largeur des colonnes
            longueur = max([len(str(c["nom"]))] + [len(_afficher(l[j - 1], c["format"])) for l in lignes])
            ws.column_dimensions[get_column_letter(j)].width = min(45, max(10, longueur + 3))
        ws.freeze_panes = "A2"
        if f.get("graphique"):
            _graphique(ws, f, der, theme)
    wb.save(str(sortie))
    return sortie


def _graphique(ws, f, der, theme):
    g = f["graphique"]
    idx = _index_colonnes(f)
    je = idx.get(g["etiquettes"].strip().lower())
    jv = [idx[v.strip().lower()] for v in g["valeurs"] if v.strip().lower() in idx]
    if je is None or not jv or der < 2:
        return
    ch = {"barres": BarChart, "courbes": LineChart, "camembert": PieChart}[g["forme"]]()
    ch.title = g["titre"]
    ch.height, ch.width = 8, 16
    if g["forme"] == "camembert":
        jv = jv[:1]
    for j in jv:
        ch.add_data(Reference(ws, min_col=j + 1, min_row=1, max_row=der), titles_from_data=True)
    ch.set_categories(Reference(ws, min_col=je + 1, min_row=2, max_row=der))
    if g["forme"] != "camembert":
        for k, s in enumerate(ch.series):
            couleur = theme.palette_graphiques[k % len(theme.palette_graphiques)].lstrip("#")
            s.graphicalProperties.solidFill = couleur
            s.graphicalProperties.line.solidFill = couleur
    ws.add_chart(ch, f"{get_column_letter(len(f['colonnes']) + 2)}2")
