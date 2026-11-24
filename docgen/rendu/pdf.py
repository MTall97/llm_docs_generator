"""JSON → PDF avec fpdf2 (police TTF du thème pour l'Unicode)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from ..theme import Theme
from .images import produire_image


class _PDF(FPDF):
    def __init__(self, theme: Theme, titre: str, **kw):
        super().__init__(**kw)
        self.theme, self.titre_doc = theme, titre
        m = theme.marge_mm
        self.set_margins(m, m, m)
        self.set_auto_page_break(True, m)
        reg, gras = theme.chemin_police(theme.police_texte), theme.chemin_police(theme.police_titre)
        if not reg:
            raise FileNotFoundError(f"police introuvable : {theme.police_texte}")
        self.add_font("T", "", str(reg))
        self.add_font("T", "B", str(gras or reg))
        self.add_font("T", "I", str(reg))  # pas d'italique fourni : on garde le romain
        self.set_title(titre)
        self.set_creator("docgen")

    def header(self):
        if self.page_no() == 1:
            return
        if self.theme.logo and Path(self.theme.logo).is_file():
            self.image(self.theme.logo, x=self.w - self.r_margin - 15, y=6, h=8)
        self.set_font("T", "", 8)
        self.set_text_color(*self.theme.rgb("secondaire"))
        self.set_y(8)
        self.cell(0, 5, self.titre_doc[:90])
        self.set_y(self.t_margin)

    def footer(self):
        self.set_y(-12)
        self.set_font("T", "", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, str(self.page_no()), align="C")

    # -- éléments ---------------------------------------------------------------
    def texte(self, t: str, taille=None, couleur="texte", style="", h=None):
        taille = taille or self.theme.taille_texte
        self.set_font("T", style, taille)
        self.set_text_color(*self.theme.rgb(couleur))
        self.multi_cell(0, h or taille * 0.5, t, align="L", new_x="LMARGIN", new_y="NEXT")

    def titre(self, t: str, niveau: int):
        tailles = {0: 24, 1: 16, 2: 13, 3: 26}  # 3 : titre de diapositive
        if self.get_y() > self.h - 50:
            self.add_page()
        self.ln(4 if niveau else 0)
        self.texte(t, tailles[niveau], "primaire", "B", tailles[niveau] * 0.55)
        if niveau in (1, 3):
            self.set_draw_color(*self.theme.rgb("accent"))
            self.set_line_width(0.6)
            self.line(self.l_margin, self.get_y() + 1, self.l_margin + 25, self.get_y() + 1)
            self.ln(3)
        self.ln(2)

    def liste(self, elements, ordonnee=False):
        self.set_font("T", "", self.theme.taille_texte)
        for i, e in enumerate(elements, 1):
            puce = f"{i}." if ordonnee else "•"
            self.set_text_color(*self.theme.rgb("accent"))
            self.cell(7, self.theme.taille_texte * 0.5, puce)
            self.set_text_color(*self.theme.rgb("texte"))
            self.multi_cell(0, self.theme.taille_texte * 0.5, e, new_x="LMARGIN", new_y="NEXT")
            self.ln(0.8)

    def tableau(self, entetes, lignes, legende=None):
        n = len(entetes)
        self.set_font("T", "", self.theme.taille_texte - 1.5)
        self.set_text_color(*self.theme.rgb("texte"))
        self.set_draw_color(200, 200, 200)
        tete = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=self.theme.rgb("primaire"))
        with self.table(headings_style=tete, line_height=5.5, cell_fill_color=(245, 247, 250),
                        cell_fill_mode="ROWS", first_row_as_headings=True) as t:
            r = t.row()
            for e in entetes:
                r.cell(str(e))
            for l in lignes:
                r = t.row()
                for c in (list(l) + [""] * n)[:n]:
                    r.cell(_fmt(c))
        if legende:
            self.texte(legende, self.theme.taille_texte - 2, "secondaire", "I")
        self.ln(2)

    def citation(self, texte, auteur=None):
        y0 = self.get_y()
        self.set_x(self.l_margin + 6)
        self.set_font("T", "I", self.theme.taille_texte + 1)
        self.set_text_color(*self.theme.rgb("primaire"))
        self.multi_cell(self.epw - 6, 6, f"« {texte} »", new_x="LMARGIN", new_y="NEXT")
        if auteur:
            self.set_x(self.l_margin + 6)
            self.set_font("T", "", self.theme.taille_texte - 1)
            self.set_text_color(*self.theme.rgb("secondaire"))
            self.cell(0, 6, f"— {auteur}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*self.theme.rgb("accent"))
        self.set_line_width(1.2)
        self.line(self.l_margin + 1, y0, self.l_margin + 1, self.get_y())
        self.ln(2)

    def image_bloc(self, bloc, dossier, base, largeur_max=None, x=None):
        chemin, msg = produire_image(bloc, dossier, self.theme, base)
        if not chemin:
            self.texte(f"⚠ {msg}", self.theme.taille_texte - 2, "accent")
            return
        icone = bloc["type"] == "icone"
        largeur = (min(50, largeur_max * 0.4) if largeur_max else 16) if icone else (largeur_max or self.epw * 0.85)
        from PIL import Image
        with Image.open(chemin) as im:
            hauteur = largeur * im.height / im.width
        if hauteur > self.h * 0.55:
            hauteur = self.h * 0.55
            largeur = hauteur * im.width / im.height
        if self.get_y() + hauteur > self.h - self.b_margin:
            self.add_page()
        xx = x if x is not None else (self.l_margin + (self.epw - largeur) / 2 if not icone else self.l_margin)
        self.image(str(chemin), x=xx, w=largeur, h=hauteur)
        if bloc.get("legende"):
            self.texte(bloc["legende"], self.theme.taille_texte - 2, "secondaire", "I")
        self.ln(2)


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return str(v)


def _bloc(pdf: _PDF, b, dossier, base):
    t = b["type"]
    if t == "paragraphe":
        pdf.texte(b["texte"])
        pdf.ln(2)
    elif t == "liste":
        pdf.liste(b["elements"], b.get("ordonnee", False))
        pdf.ln(1)
    elif t == "tableau":
        pdf.tableau(b["entetes"], b["lignes"], b.get("legende"))
    elif t == "citation":
        pdf.citation(b["texte"], b.get("auteur"))
    else:
        pdf.image_bloc(b, dossier, base)


def rendre_pdf(d: dict, sortie: Path, theme: Theme | None = None, base: Path | None = None) -> Path:
    theme = theme or Theme()
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        dossier = Path(tmp)
        if d["type"] == "presentation":
            pdf = _pdf_presentation(d, theme, dossier, base)
        else:
            pdf = _PDF(theme, d["titre"], format="A4")
            pdf.add_page()
            if theme.logo and Path(theme.logo).is_file():
                pdf.image(theme.logo, h=14)
                pdf.ln(4)
            pdf.titre(d["titre"], 0)
            if d.get("sous_titre"):
                pdf.texte(d["sous_titre"], 13, "secondaire")
            pdf.ln(4)
            if d["type"] == "document":
                for s in d["sections"]:
                    pdf.titre(s["titre"], 1)
                    for b in s["blocs"]:
                        _bloc(pdf, b, dossier, base)
            else:  # classeur : une section par feuille, valeurs calculées
                from .xlsx import valeurs_calculees
                for f in d["feuilles"]:
                    pdf.titre(f["nom"], 1)
                    entetes, lignes = valeurs_calculees(f)
                    pdf.tableau(entetes, lignes)
        pdf.output(str(sortie))
    return sortie


def _pdf_presentation(d, theme, dossier, base) -> _PDF:
    """Une page 16:9 par diapositive."""
    pdf = _PDF(theme, d["titre"], orientation="L", format=(190.5, 338.7))
    pdf.set_auto_page_break(False)
    for i, dia in enumerate(d["diapositives"]):
        pdf.add_page()
        m = dia["mise_en_page"]
        if m == "titre" or (i == 0 and m not in ("points", "deux_colonnes", "image_texte")):
            pdf.set_fill_color(*theme.rgb("primaire"))
            pdf.rect(0, 0, pdf.w, pdf.h, "F")
            pdf.set_y(pdf.h * 0.35)
            pdf.texte(dia.get("titre") or dia.get("texte", d["titre"]), 32, "fond", "B", 14)
            sous = dia.get("sous_titre") or dia.get("legende") or d.get("sous_titre")
            if sous:
                pdf.ln(3)
                pdf.texte(sous, 16, "fond")
            continue
        if m == "chiffre_cle":
            pdf.titre(dia["titre"], 3)
            pdf.set_y(pdf.h * 0.35)
            pdf.set_font("T", "B", 72)
            pdf.set_text_color(*theme.rgb("accent"))
            pdf.cell(0, 30, dia["chiffre"], align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("T", "", 18)
            pdf.set_text_color(*theme.rgb("texte"))
            pdf.multi_cell(0, 9, dia["legende"], align="C")
            continue
        if m == "citation":
            pdf.set_y(pdf.h * 0.3)
            pdf.set_font("T", "I", 26)
            pdf.set_text_color(*theme.rgb("primaire"))
            pdf.multi_cell(0, 13, f"« {dia['texte']} »", align="C", new_x="LMARGIN", new_y="NEXT")
            if dia.get("auteur"):
                pdf.ln(4)
                pdf.texte(f"— {dia['auteur']}", 16, "secondaire")
            continue
        pdf.titre(dia["titre"], 3)
        taille = theme.taille_texte + 9
        if m == "points":
            _points(pdf, dia["points"], taille)
        elif m == "deux_colonnes":
            y = pdf.get_y()
            l = (pdf.epw - 10) / 2
            for k, c in enumerate((dia["gauche"], dia["droite"])):
                pdf.set_xy(pdf.l_margin + k * (l + 10), y)
                pdf.set_font("T", "B", taille)
                pdf.set_text_color(*theme.rgb("secondaire"))
                pdf.multi_cell(l, 9, c["titre"], new_x="LEFT", new_y="NEXT")
                _points(pdf, c["points"], taille - 2, x=pdf.l_margin + k * (l + 10), largeur=l)
        elif m == "image_texte":
            y = pdf.get_y()
            l = pdf.epw * 0.5
            pdf.image_bloc(dia["image"], dossier, base, largeur_max=l, x=pdf.l_margin)
            pdf.set_y(y)
            _points(pdf, dia["points"], taille - 2, x=pdf.l_margin + l + 10, largeur=pdf.epw - l - 10)
    return pdf


def _points(pdf: _PDF, points, taille, x=None, largeur=0):
    x = x if x is not None else pdf.l_margin
    for p in points:
        pdf.set_x(x)
        pdf.set_font("T", "", taille)
        pdf.set_text_color(*pdf.theme.rgb("accent"))
        pdf.cell(8, taille * 0.5, "•")
        pdf.set_text_color(*pdf.theme.rgb("texte"))
        pdf.multi_cell(largeur - 8 if largeur else 0, taille * 0.5, p, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
