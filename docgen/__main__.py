"""Ligne de commande.

  python -m docgen rendre exemples/presentation.json -f pptx pdf -o sortie/pres
  python -m docgen texte compte_rendu.txt -s document -o sortie/cr
  python -m docgen plan "Le compostage en appartement" -s presentation -o plan.json
  python -m docgen rediger plan.json -s presentation -o sortie/compost
  python -m docgen sujet "Le compostage en appartement" -s document -o sortie/compost
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .rendu import FORMATS_PAR_DEFAUT, MOTEURS, rendre
from .schema import valider
from .theme import charger_theme

MODELE_DEFAUT = os.environ.get("DOCGEN_MODELE", "modeles/qwen2.5-1.5b-instruct-q4_k_m.gguf")


def _commun(p):
    p.add_argument("-o", "--sortie", required=True, help="chemin de sortie, sans extension")
    p.add_argument("-f", "--formats", nargs="+", choices=list(MOTEURS), help="formats (défaut selon la sorte)")
    p.add_argument("-t", "--theme", help="nom d'un thème de themes/ ou chemin d'un .toml")
    p.add_argument("--modele-pptx", help="modèle PowerPoint de l'utilisateur (masques de diapositives)")


def _modele(p):
    p.add_argument("-s", "--sorte", choices=["document", "presentation", "classeur"], default="document")
    p.add_argument("-m", "--modele", default=MODELE_DEFAUT, help="fichier GGUF (ou variable DOCGEN_MODELE)")
    p.add_argument("--ton", default="formel", choices=["formel", "pedagogique", "convivial", "concis"])
    p.add_argument("--sans-images", action="store_true", help="interdire graphiques, schémas et icônes")
    p.add_argument("--images", nargs="*", default=[], help="images de l'utilisateur à placer")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="docgen", description="Documents à partir d'un petit modèle de langage.")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("rendre", help="JSON → fichiers (sans modèle)")
    p.add_argument("json")
    _commun(p)
    p = sp.add_parser("texte", help="mettre en forme un texte fourni")
    p.add_argument("fichier", help="fichier texte, ou - pour l'entrée standard")
    p.add_argument("-c", "--consigne", default="", help="précision sur ce qu'on veut obtenir")
    p.add_argument("--deux-temps", action="store_true",
                   help="extraire d'abord les faits du texte, puis les mettre en forme")
    _modele(p)
    _commun(p)
    p = sp.add_parser("plan", help="sujet seul, étape 1 : proposer un plan (à modifier puis `rediger`)")
    p.add_argument("sujet")
    p.add_argument("-n", "--parties", type=int, default=5)
    p.add_argument("-o", "--sortie", required=True, help="fichier JSON du plan")
    _modele(p)
    p = sp.add_parser("rediger", help="sujet seul, étape 2 : rédiger à partir d'un plan JSON")
    p.add_argument("plan")
    _modele(p)
    _commun(p)
    p = sp.add_parser("sujet", help="plan puis rédaction, sans pause")
    p.add_argument("sujet")
    p.add_argument("-n", "--parties", type=int, default=5)
    _modele(p)
    _commun(p)
    a = ap.parse_args(argv)

    theme = charger_theme(getattr(a, "theme", None))
    if getattr(a, "modele_pptx", None):
        theme.modele_pptx = a.modele_pptx

    if a.cmd == "rendre":
        d = json.loads(Path(a.json).read_text(encoding="utf-8"))
        for f in rendre(d, a.sortie, a.formats, theme, base=Path(a.json).parent):
            print(f)
        return 0

    from .generation import Generateur
    if not Path(a.modele).is_file():
        sys.exit(f"modèle introuvable : {a.modele} (voir README, « Télécharger un modèle »)")
    g = Generateur(a.modele)
    fichiers = [Path(i).name for i in a.images]
    base = Path(a.images[0]).parent if a.images else None
    if a.cmd == "plan":
        r = g.plan(a.sujet, a.sorte, a.parties, a.ton)
        if r.donnees is None:
            sys.exit(f"échec du plan : {r.erreur}")
        Path(a.sortie).write_text(json.dumps(r.donnees, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(r.donnees, ensure_ascii=False, indent=1))
        print(f"\nPlan écrit dans {a.sortie} ({r.secondes:.0f} s). Modifiez-le, puis : "
              f"python -m docgen rediger {a.sortie} -s {a.sorte} -o …", file=sys.stderr)
        return 0
    if a.cmd == "texte":
        texte = sys.stdin.read() if a.fichier == "-" else Path(a.fichier).read_text(encoding="utf-8")
        r = g.depuis_texte(texte, a.sorte, a.consigne, a.ton, not a.sans_images, fichiers,
                           deux_temps=a.deux_temps)
    else:
        if a.cmd == "rediger":
            plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
        else:
            rp = g.plan(a.sujet, a.sorte, a.parties, a.ton)
            if rp.donnees is None:
                sys.exit(f"échec du plan : {rp.erreur}")
            plan = rp.donnees
        print("⚠ Mode « sujet seul » : le contenu vient des connaissances limitées du modèle ; "
              "vérifiez chaque fait.", file=sys.stderr)
        r = g.rediger(plan, a.sorte, a.ton, not a.sans_images, fichiers)
    if r.donnees is None:
        sys.exit(f"échec de la génération : {r.erreur}")
    Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
    Path(a.sortie).with_suffix(".json").write_text(json.dumps(r.donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in r.corrections:
        print(f"correction : {c}", file=sys.stderr)
    for e in valider(r.donnees):
        print(f"avertissement : {e}", file=sys.stderr)
    for f in rendre(r.donnees, a.sortie, a.formats or FORMATS_PAR_DEFAUT[a.sorte], theme, base, verifier=False):
        print(f)
    print(f"{r.secondes:.0f} s, {r.jetons_sortie} jetons produits", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
