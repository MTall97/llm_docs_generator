"""JSON → PowerPoint (python-pptx).

Sans modèle fourni : diapositives 16:9 dessinées à partir du thème.
Avec un modèle .pptx de l'utilisateur : on utilise ses masques (dispositions
« Titre », « Titre et contenu », « Deux contenus », « Titre seul ») et on
remplit leurs espaces réservés, pour garder sa charte graphique.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

from ..theme import Theme
from .images import produire_image

FORMES = {"barres": XL_CHART_TYPE.COLUMN_CLUSTERED, "courbes": XL_CHART_TYPE.LINE_MARKERS,
          "camembert": XL_CHART_TYPE.PIE}


def _rgb(theme, cle):
    return RGBColor(*theme.rgb(cle))


def document_vers_presentation(d: dict) -> dict:
    """Conversion simple : une diapositive par section (listes et premières phrases)."""
    dias = [{"mise_en_page": "titre", "titre": d["titre"], "sous_titre": d.get("sous_titre", "")}]
    for s in d["sections"]:
        points, image = [], None
        for b in s["blocs"]:
            if b["type"] == "liste":
                points += b["elements"]
            elif b["type"] == "paragraphe":
                points.append(b["texte"].split(". ")[0].rstrip(".") + ".")
            elif b["type"] in ("graphique", "schema", "icone", "image") and image is None:
                image = b
            elif b["type"] == "citation":
                dias.append({"mise_en_page": "citation", "texte": b["texte"], "auteur": b.get("auteur", "")})
        points = [p[:160] for p in points][:6] or [s["titre"]]
        if image:
            dias.append({"mise_en_page": "image_texte", "titre": s["titre"], "image": image, "points": points})
        else:
            dias.append({"mise_en_page": "points", "titre": s["titre"], "points": points})
    return {"type": "presentation", "titre": d["titre"], "diapositives": dias}


class _Rendu:
    def __init__(self, theme: Theme, dossier: Path, base):
        self.theme, self.dossier, self.base = theme, dossier, base
        self.modele = bool(theme.modele_pptx and Path(theme.modele_pptx).is_file())
        self.prs = Presentation(theme.modele_pptx) if self.modele else Presentation()
        if self.modele:  # on retire les diapositives d'exemple éventuelles du modèle
            ids = self.prs.slides._sldIdLst
            for sld in list(ids):
                self.prs.part.drop_rel(sld.rId)
                ids.remove(sld)
        else:
            self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.W, self.H = self.prs.slide_width, self.prs.slide_height
        self.marge = Inches(0.6)

    # -- outils ----------------------------------------------------------------------
    def disposition(self, *noms, defaut=6):
        """Cherche une disposition du masque par nom (anglais ou français)."""
        for lay in self.prs.slide_layouts:
            if lay.name.lower() in [n.lower() for n in noms]:
                return lay
        lays = self.prs.slide_layouts
        return lays[min(defaut, len(lays) - 1)]

    def zone_texte(self, slide, x, y, w, h, lignes, taille, couleur="texte", gras=False,
                   puces=False, align=PP_ALIGN.LEFT, ancre=MSO_ANCHOR.TOP):
        tf = slide.shapes.add_textbox(x, y, w, h).text_frame
        tf.word_wrap = True
        tf.vertical_anchor = ancre
        for i, l in enumerate(lignes if isinstance(lignes, list) else [lignes]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            if puces:
                r0 = p.add_run()
                r0.text = "■  "
                r0.font.size = Pt(taille * 0.6)
                r0.font.color.rgb = _rgb(self.theme, "accent")
            r = p.add_run()
            r.text = l
            r.font.size, r.font.bold, r.font.name = Pt(taille), gras, self.theme.police_pptx
            r.font.color.rgb = _rgb(self.theme, couleur)
            p.alignment = align
            p.space_after = Pt(taille * 0.6)
        return tf

    def titre(self, slide, texte):
        self.zone_texte(slide, self.marge, Inches(0.4), self.W - 2 * self.marge, Inches(1.0),
                        texte, 30, "primaire", gras=True, ancre=MSO_ANCHOR.MIDDLE)
        barre = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, self.marge, Inches(1.4), Inches(1.2), Inches(0.07))
        barre.fill.solid()
        barre.fill.fore_color.rgb = _rgb(self.theme, "accent")
        barre.line.fill.background()
        if self.theme.logo and Path(self.theme.logo).is_file():
            slide.shapes.add_picture(self.theme.logo, self.W - self.marge - Inches(1), Inches(0.35), height=Inches(0.5))

    def image(self, slide, bloc, x, y, w, h):
        if bloc["type"] == "graphique":
            self.graphique(slide, bloc, x, y, w, h)
            return
        chemin, msg = produire_image(bloc, self.dossier, self.theme, self.base)
        if not chemin:
            self.zone_texte(slide, x, y, w, h, f"⚠ {msg}", 12, "accent")
            return
        from PIL import Image
        with Image.open(chemin) as im:
            ratio = im.width / im.height
        if bloc["type"] == "icone":
            w = h = min(w, h, Inches(2.2))
        if w / h > ratio:
            w2, h2 = int(h * ratio), h
        else:
            w2, h2 = w, int(w / ratio)
        slide.shapes.add_picture(str(chemin), x + (w - w2) // 2, y + (h - h2) // 2, w2, h2)

    def graphique(self, slide, g, x, y, w, h):
        """Graphique natif PowerPoint : modifiable par l'utilisateur."""
        n = len(g["etiquettes"])
        data = CategoryChartData()
        data.categories = [str(e) for e in g["etiquettes"]]
        series = g["series"][:1] if g["forme"] == "camembert" else g["series"]
        for s in series:
            data.add_series(s["nom"], (list(s["valeurs"]) + [0] * n)[:n])
        ch = slide.shapes.add_chart(FORMES[g["forme"]], x, y, w, h, data).chart
        ch.has_title = bool(g.get("titre"))
        if ch.has_title:
            ch.chart_title.text_frame.text = g["titre"]
            ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
        ch.has_legend = g["forme"] == "camembert" or len(series) > 1
        if ch.has_legend:
            ch.legend.position = XL_LEGEND_POSITION.BOTTOM
            ch.legend.include_in_layout = False
        pal = self.theme.palette_graphiques
        if g["forme"] == "camembert":
            for i, pt in enumerate(ch.plots[0].series[0].points):
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = RGBColor.from_string(pal[i % len(pal)].lstrip("#"))
        else:
            for i, s in enumerate(ch.plots[0].series):
                c = RGBColor.from_string(pal[i % len(pal)].lstrip("#"))
                if g["forme"] == "barres":
                    s.format.fill.solid()
                    s.format.fill.fore_color.rgb = c
                else:
                    s.format.line.color.rgb = c

    # -- diapositives ------------------------------------------------------------------
    def diapo(self, dia, d, i):
        if self.modele:
            return self.diapo_modele(dia, d)
        m = dia["mise_en_page"]
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # vierge
        W, H, mg = self.W, self.H, self.marge
        larg = W - 2 * mg
        if m == "titre":
            fond = slide.background.fill
            fond.solid()
            fond.fore_color.rgb = _rgb(self.theme, "primaire")
            self.zone_texte(slide, mg, Inches(2.4), larg, Inches(1.6), dia["titre"], 44, "fond", True,
                            ancre=MSO_ANCHOR.BOTTOM)
            if dia.get("sous_titre"):
                self.zone_texte(slide, mg, Inches(4.2), larg, Inches(1.2), dia["sous_titre"], 22, "fond")
        elif m == "points":
            self.titre(slide, dia["titre"])
            self.zone_texte(slide, mg, Inches(1.8), larg, H - Inches(2.3), dia["points"], 22, puces=True)
        elif m == "deux_colonnes":
            self.titre(slide, dia["titre"])
            l = (larg - Inches(0.5)) // 2
            for k, c in enumerate((dia["gauche"], dia["droite"])):
                x = mg + k * (l + Inches(0.5))
                self.zone_texte(slide, x, Inches(1.8), l, Inches(0.7), c["titre"], 24, "secondaire", True)
                self.zone_texte(slide, x, Inches(2.6), l, H - Inches(3.1), c["points"], 20, puces=True)
        elif m == "image_texte":
            self.titre(slide, dia["titre"])
            l = int(larg * 0.55)
            self.image(slide, dia["image"], mg, Inches(1.8), l, H - Inches(2.3))
            self.zone_texte(slide, mg + l + Inches(0.4), Inches(1.9), larg - l - Inches(0.4), H - Inches(2.4),
                            dia["points"], 20, puces=True)
        elif m == "chiffre_cle":
            self.titre(slide, dia["titre"])
            self.zone_texte(slide, mg, Inches(2.2), larg, Inches(2.2), dia["chiffre"], 96, "accent", True,
                            align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE)
            self.zone_texte(slide, mg, Inches(4.6), larg, Inches(1.5), dia["legende"], 24,
                            align=PP_ALIGN.CENTER)
        elif m == "citation":
            self.zone_texte(slide, Inches(1.5), Inches(1.8), W - Inches(3), Inches(3), f"« {dia['texte']} »",
                            32, "primaire", align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE)
            if dia.get("auteur"):
                self.zone_texte(slide, Inches(1.5), Inches(5.0), W - Inches(3), Inches(0.8), f"— {dia['auteur']}",
                                20, "secondaire", align=PP_ALIGN.CENTER)
        return slide

    def diapo_modele(self, dia, d):
        """Remplit les espaces réservés des masques de l'utilisateur."""
        m = dia["mise_en_page"]
        noms = {"titre": (("title slide", "diapositive de titre"), 0),
                "points": (("title and content", "titre et contenu"), 1),
                "deux_colonnes": (("two content", "deux contenus"), 3)}
        (cand, defaut) = noms.get(m, (("title only", "titre seul"), 5))
        slide = self.prs.slides.add_slide(self.disposition(*cand, defaut=defaut))
        ph = {p.placeholder_format.idx: p for p in slide.placeholders}
        if slide.shapes.title is not None:
            slide.shapes.title.text = dia.get("titre") or ("Citation" if m == "citation" else "")
        corps = [p for i, p in sorted(ph.items()) if i != 0]

        def remplir(p, lignes):
            tf = p.text_frame
            for k, l in enumerate(lignes):
                (tf.paragraphs[0] if k == 0 else tf.add_paragraph()).text = l

        if m == "titre" and corps:
            remplir(corps[0], [dia.get("sous_titre", "")])
        elif m == "points" and corps:
            remplir(corps[0], dia["points"])
        elif m == "deux_colonnes" and len(corps) >= 2:
            remplir(corps[0], [dia["gauche"]["titre"], *dia["gauche"]["points"]])
            remplir(corps[1], [dia["droite"]["titre"], *dia["droite"]["points"]])
        else:
            for p in corps:  # espaces réservés inutilisés : on les retire
                p._element.getparent().remove(p._element)
            haut, larg = Inches(1.8), self.W - 2 * self.marge
            if m == "image_texte":
                l = int(larg * 0.55)
                self.image(slide, dia["image"], self.marge, haut, l, self.H - haut - Inches(0.5))
                self.zone_texte(slide, self.marge + l + Inches(0.4), haut, larg - l - Inches(0.4),
                                self.H - haut - Inches(0.5), dia["points"], 20, puces=True)
            elif m == "chiffre_cle":
                self.zone_texte(slide, self.marge, haut, larg, Inches(2.2), dia["chiffre"], 96, "accent", True,
                                align=PP_ALIGN.CENTER)
                self.zone_texte(slide, self.marge, haut + Inches(2.4), larg, Inches(1.4), dia["legende"], 24,
                                align=PP_ALIGN.CENTER)
            elif m == "citation":
                self.zone_texte(slide, self.marge, haut, larg, Inches(3), f"« {dia['texte']} »"
                                + (f"\n— {dia['auteur']}" if dia.get("auteur") else ""), 30, "primaire",
                                align=PP_ALIGN.CENTER)
        return slide


def rendre_pptx(d: dict, sortie: Path, theme: Theme | None = None, base: Path | None = None) -> Path:
    theme = theme or Theme()
    if d["type"] == "document":
        d = document_vers_presentation(d)
    elif d["type"] != "presentation":
        raise ValueError("PowerPoint : seuls les documents et les présentations sont pris en charge")
    sortie = Path(sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        r = _Rendu(theme, Path(tmp), base)
        dias = d["diapositives"]
        if dias[0]["mise_en_page"] != "titre":  # une page de titre est toujours ajoutée
            dias = [{"mise_en_page": "titre", "titre": d["titre"], "sous_titre": d.get("sous_titre", "")}] + dias
        for i, dia in enumerate(dias):
            slide = r.diapo(dia, d, i)
            if dia.get("notes"):
                slide.notes_slide.notes_text_frame.text = dia["notes"]
        r.prs.core_properties.title = d["titre"]
        r.prs.save(str(sortie))
    return sortie
