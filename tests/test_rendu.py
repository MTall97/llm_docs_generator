"""Tests des moteurs de rendu, sans modèle : JSON d'exemple → fichiers valides."""
import copy
import json
import shutil
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pptx import Presentation

from docgen.nettoyage import nettoyer
from docgen.rendu import rendre
from docgen.rendu.images import mermaid_vers_dot, trouver_icone
from docgen.rendu.xlsx import nombre, traduire_formule, valeurs_calculees
from docgen.schema import schema_generation, valider
from docgen.theme import charger_theme

EX = Path(__file__).resolve().parent.parent / "exemples"


def charger(nom):
    return json.loads((EX / f"{nom}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nom", ["document", "presentation", "classeur"])
def test_exemples_conformes(nom):
    assert valider(charger(nom)) == []


@pytest.mark.parametrize("nom,formats", [
    ("document", ["md", "pdf", "pptx", "xlsx"]),
    ("presentation", ["md", "pdf", "pptx"]),
    ("classeur", ["md", "pdf", "xlsx"]),
])
@pytest.mark.parametrize("theme", [None, "nature"])
def test_rendu_tous_formats(tmp_path, nom, formats, theme):
    fichiers = rendre(charger(nom), tmp_path / nom, formats, charger_theme(theme), base=EX)
    assert [f.suffix[1:] for f in fichiers] == formats
    for f in fichiers:
        assert f.stat().st_size > 0
        if f.suffix == ".pdf":
            assert f.read_bytes()[:5] == b"%PDF-"
        elif f.suffix == ".pptx":
            assert len(Presentation(str(f)).slides) >= 2
        elif f.suffix == ".xlsx":
            assert load_workbook(f).sheetnames
        elif f.suffix == ".md":
            assert f.read_text(encoding="utf-8").startswith("# ")


def test_markdown_images_et_tableau(tmp_path):
    md = rendre(charger("document"), tmp_path / "doc", ["md"])[0].read_text(encoding="utf-8")
    assert "| Indicateur | 2024 | 2025 |" in md
    assert "```mermaid" in md                      # Mermaid conservé tel quel en Markdown
    images = list((tmp_path / "doc_images").glob("*.png"))
    assert len(images) >= 4                         # 2 graphiques, 1 schéma Graphviz, 1 icône


def test_pptx_graphique_natif_et_notes(tmp_path):
    f = rendre(charger("presentation"), tmp_path / "p", ["pptx"])[0]
    prs = Presentation(str(f))
    assert any(sh.has_chart for s in prs.slides for sh in s.shapes)
    assert any(s.has_notes_slide and "croissance" in s.notes_slide.notes_text_frame.text for s in prs.slides)


def test_pptx_avec_modele_utilisateur(tmp_path):
    modele = tmp_path / "modele.pptx"
    Presentation().save(str(modele))               # masques par défaut de PowerPoint
    theme = charger_theme()
    theme.modele_pptx = str(modele)
    f = rendre(charger("presentation"), tmp_path / "p", ["pptx"], theme)[0]
    prs = Presentation(str(f))
    assert len(prs.slides) == len(charger("presentation")["diapositives"])
    assert prs.slides[1].shapes.title.text == "L'année en bref"


def test_xlsx_formules_et_totaux(tmp_path):
    f = rendre(charger("classeur"), tmp_path / "c", ["xlsx"])[0]
    ws = load_workbook(f)["Dépenses"]
    assert ws["D2"].value == "=B2 * C2"
    assert ws["D6"].value == "=SUM(D2:D5)"
    assert ws["C6"].value == "=COUNT(C2:C5)"
    assert ws["B2"].value == 2.5                   # « 2,50 » converti en nombre
    assert ws._charts                              # graphique natif


def test_xlsx_recalcul_libreoffice(tmp_path):
    """Vérifie que les formules donnent le bon résultat (si LibreOffice est installé)."""
    if not shutil.which("soffice"):
        pytest.skip("LibreOffice absent")
    import subprocess
    f = rendre(charger("classeur"), tmp_path / "c", ["xlsx"])[0]
    subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(tmp_path / "r"), str(f)],
                   capture_output=True, timeout=120)
    ws = load_workbook(tmp_path / "r" / "c.xlsx", data_only=True)["Dépenses"]
    assert ws["D6"].value == pytest.approx(2420)


def test_valeurs_calculees_apercu():
    entetes, lignes = valeurs_calculees(charger("classeur")["feuilles"][0])
    assert lignes[0][3] == "1 000,00 €"
    assert lignes[-1][3] == "2 420,00 €"


def test_traduire_formule():
    f = {"colonnes": [{"nom": "Prix", "format": "monnaie"}, {"nom": "Quantité", "format": "nombre"}]}
    assert traduire_formule("{Prix} * {quantité}", f, 7) == "=A7 * B7"
    assert traduire_formule("=[Prix]*2", f, 3) == "=A3*2"
    with pytest.raises(ValueError):
        traduire_formule("{Inconnue} + 1", f, 2)


@pytest.mark.parametrize("brut,attendu", [("1 200,50 €", 1200.5), ("12 %", 12), (3, 3), ("abc", None), (None, None)])
def test_nombre(brut, attendu):
    assert nombre(brut) == attendu


def test_mermaid_vers_dot():
    dot = mermaid_vers_dot("graph LR\n A[Début] -->|ok| B(Fin)\n B --> C{Choix}")
    assert "rankdir=LR" in dot and '"A" -> "B" [label="ok"]' in dot and 'label="Choix"' in dot


def test_icones():
    assert trouver_icone("budget") == "wallet"
    assert trouver_icone("Écologie") == "leaf"
    assert trouver_icone("zzzz") is None


def test_image_echouee_ne_bloque_pas(tmp_path):
    d = charger("document")
    d["sections"][0]["blocs"].append({"type": "schema", "langage": "graphviz", "code": "digraph { -> -> }"})
    d["sections"][0]["blocs"].append({"type": "image", "chemin": "absente.png"})
    for f in rendre(d, tmp_path / "d", ["md", "pdf", "pptx"]):
        assert f.stat().st_size > 0
    assert "⚠️" in (tmp_path / "d.md").read_text(encoding="utf-8")


def test_validation_refuse_structure_fausse():
    d = charger("presentation")
    d["diapositives"][1]["mise_en_page"] = "inventee"
    assert valider(d)
    assert valider({"type": "lettre"})
    with pytest.raises(ValueError):
        rendre(d, "/tmp/inutile", ["md"])


def test_nettoyage_classeur():
    d = {"type": "classeur", "titre": "t", "feuilles": [{"nom": "F", "colonnes": [
        {"nom": "A", "format": "texte"}, {"nom": "B", "format": "nombre", "formule": "14"}],
        "lignes": [["_A_", "_B_"], ["x", "null"], ["y"]], "totaux": [{"colonne": "Z", "fonction": "SOMME"}]}]}
    d, corr = nettoyer(copy.deepcopy(d))
    f = d["feuilles"][0]
    assert "formule" not in f["colonnes"][1]
    assert f["lignes"] == [["x", None], ["y", None]]
    assert f["totaux"] == []
    assert len(corr) >= 3


def test_nettoyage_formule_melangee():
    d = {"type": "classeur", "titre": "t", "feuilles": [{"nom": "F", "colonnes": [
        {"nom": "Quantité", "format": "nombre"}, {"nom": "Prix", "format": "monnaie"},
        {"nom": "Valeur", "format": "monnaie", "formule": "C{Quantité} * {Prix}2"}], "lignes": [[2, 3, None]]}]}
    d, corr = nettoyer(d)
    assert d["feuilles"][0]["colonnes"][2]["formule"] == "{Quantité} * {Prix}"
    assert traduire_formule("{Quantité} * {Prix}", d["feuilles"][0], 2) == "=A2 * B2"


def test_schema_generation_sans_maxlength():
    s = json.dumps(schema_generation("document"))
    assert "maxLength" not in s and '"enum": ["a.png"]' not in s
    s = json.dumps(schema_generation("presentation", fichiers=["a.png"]))
    assert '"enum": ["a.png"]' in s
