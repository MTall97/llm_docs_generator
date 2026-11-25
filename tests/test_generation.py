"""Tests de génération : ignorés si llama-cpp-python ou le modèle sont absents.

Modèle utilisé : variable DOCGEN_MODELE_TEST, sinon le plus petit de modeles/.
"""
import os
from pathlib import Path

import pytest

from docgen.rendu import rendre
from docgen.schema import valider

RACINE = Path(__file__).resolve().parent.parent
MODELE = os.environ.get("DOCGEN_MODELE_TEST") or str(RACINE / "modeles" / "qwen2.5-0.5b-instruct-q4_k_m.gguf")

pytest.importorskip("llama_cpp")
pytestmark = pytest.mark.skipif(not Path(MODELE).is_file(), reason=f"modèle absent : {MODELE}")

TEXTE = ("Le club de lecture se réunit le premier jeudi du mois. Il compte 18 membres. "
         "En 2026, il a lu 11 romans, dont 4 d'autrices africaines. La cotisation annuelle est de 15 euros.")


@pytest.fixture(scope="module")
def gen():
    from docgen.generation import Generateur
    return Generateur(MODELE, n_ctx=4096)


@pytest.mark.parametrize("sorte", ["document", "presentation", "classeur"])
def test_texte_vers_json_valide_et_rendu(gen, tmp_path, sorte):
    r = gen.depuis_texte(TEXTE, sorte, max_jetons=1500)
    assert r.donnees is not None, r.erreur          # la grammaire garantit un JSON analysable…
    structure = [e for e in valider(r.donnees) if "cellules pour" not in e and "la série" not in e]
    assert structure == [], structure               # …et conforme au schéma
    assert all(f.stat().st_size > 0 for f in rendre(r.donnees, tmp_path / sorte, verifier=False))


def test_plan_puis_redaction(gen):
    p = gen.plan("Le compostage en appartement", "document", nb_parties=2)
    assert p.donnees and len(p.donnees["parties"]) >= 2
    p.donnees["parties"] = p.donnees["parties"][:2]
    r = gen.rediger(p.donnees, "document", max_jetons=600)
    assert r.donnees and r.donnees["sections"]


def test_deux_temps(gen):
    r = gen.depuis_texte(TEXTE, "document", deux_temps=True, max_jetons=1200)
    assert r.etapes and r.etapes[0]["faits"]["faits"]   # étape 1 : liste de faits
    assert r.donnees is not None, r.erreur
