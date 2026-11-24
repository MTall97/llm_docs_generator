"""Synthèse des mesures du banc d'essai → banc/RESULTATS.md."""
from __future__ import annotations

import csv
import json
import statistics as st
from pathlib import Path

RACINE = Path(__file__).resolve().parent
ORDRE = ["qwen2.5-0.5b", "qwen2.5-0.5b-sans-exemple", "qwen2.5-1.5b", "qwen2.5-3b"]


def _f(v):
    return float(v) if v not in ("", None) else None


def _pct(x):
    return "–" if x is None else f"{100 * x:.0f} %"


def _moy(vals):
    vals = [v for v in vals if v is not None]
    return st.mean(vals) if vals else None


def main():
    import sys
    sys.path.insert(0, str(RACINE))
    from lancer import recopie_exemple  # recalculée : la mesure a été resserrée après le banc
    lignes, machines = {}, {}
    for d in sorted((RACINE / "resultats").iterdir()):
        if (d / "mesures.csv").is_file():
            lignes[d.name] = list(csv.DictReader(open(d / "mesures.csv", encoding="utf-8")))
            for l in lignes[d.name]:
                j = d / f"{l['id']}.json"
                l["recopie_exemple"] = recopie_exemple(l["sorte"], json.loads(j.read_text())) if j.is_file() else 0
            machines[d.name] = json.loads((d / "machine.json").read_text())
    modeles = [m for m in ORDRE if m in lignes] + [m for m in lignes if m not in ORDRE]
    demandes = {d["id"]: d for d in json.loads((RACINE / "demandes.json").read_text(encoding="utf-8"))}

    md = ["# Résultats du banc d'essai", "",
          "Généré par `python banc/rapport.py` à partir de `banc/resultats/*/mesures.csv`.",
          "Machine : CPU 4 cœurs, 15 Go de RAM, sans GPU ; modèles GGUF Q4_K_M ; llama-cpp-python, 4 threads, "
          "température 0,2.", "",
          "## Synthèse par modèle", "",
          "| | " + " | ".join(modeles) + " |", "|---|" + "---|" * len(modeles)]

    def ligne(titre, f):
        md.append(f"| {titre} | " + " | ".join(f(m) for m in modeles) + " |")

    ligne("Taille du fichier", lambda m: f"{machines[m]['fichier_mo']} Mo")
    ligne("Mémoire max du processus", lambda m: f"{machines[m]['memoire_max_mo']} Mo")
    ligne("Chargement du modèle", lambda m: f"{machines[m]['chargement_s']} s")
    ligne("JSON valide (structure du schéma)",
          lambda m: f"{sum(l['json_valide'] == 'True' for l in lignes[m])}/{len(lignes[m])}")
    ligne("Fichiers produits", lambda m: f"{sum(l['rendu_ok'] == 'True' for l in lignes[m])}/{len(lignes[m])}")
    ligne("Échecs « limite de jetons » (boucle)",
          lambda m: str(sum("limite de jetons" in l["erreur"] for l in lignes[m])))
    ligne("Corrections mécaniques (moyenne)", lambda m: f"{_moy([_f(l['corrections']) for l in lignes[m]]):.1f}")
    ligne("Recopie de l'exemple de la consigne (demandes touchées)",
          lambda m: str(sum((_f(l.get("recopie_exemple")) or 0) > 0 for l in lignes[m])))
    ligne("Vitesse (jetons produits / s, médiane)", lambda m: f"{st.median(_f(l['jetons_par_s']) for l in lignes[m]):.1f}")
    for sorte in ("document", "presentation", "classeur"):
        ligne(f"Temps médian, {sorte} depuis un texte",
              lambda m, s=sorte: f"{st.median([_f(l['secondes']) for l in lignes[m] if l['sorte'] == s and l['mode'] == 'texte']):.0f} s")
    ligne("Temps médian, sujet seul (plan + parties)",
          lambda m: f"{st.median([_f(l['secondes']) for l in lignes[m] if l['mode'] == 'sujet']):.0f} s")
    texte = lambda m: [l for l in lignes[m] if l["mode"] == "texte" and l["json_valide"] == "True"]
    ligne("Fidélité auto. : chiffres absents de la source (moyenne)", lambda m: _pct(_moy([_f(l["chiffres_inventes"]) for l in texte(m)])))
    ligne("Couverture : chiffres de la source repris (moyenne)", lambda m: _pct(_moy([_f(l["chiffres_repris"]) for l in texte(m)])))
    ligne("Mots pleins absents de la source (moyenne)", lambda m: _pct(_moy([_f(l["mots_hors_source"]) for l in texte(m)])))

    # Relecture manuelle (banc/relecture.csv)
    rel = list(csv.DictReader(open(RACINE / "relecture.csv", encoding="utf-8")))
    for note, nom in (("✅", "fidèle et complet"), ("🟡", "incomplet ou ajout mineur"),
                      ("❌", "information fausse")):
        ligne(f"Relecture manuelle, {note} {nom}",
              lambda m, n=note: (f"{sum(r['note'] == n for r in rel if r['modele'] == m)}/"
                                 f"{sum(r['modele'] == m for r in rel)}") if any(r['modele'] == m for r in rel) else "–")
    md += ["", "Lecture : les lignes « Fidélité », « Couverture » et « Mots pleins » portent sur les demandes « texte "
           "fourni » dont le JSON est valide ; la relecture manuelle sur les 11 demandes « texte fourni ». "
           "« Recopie de l'exemple » compte les demandes dont la sortie reprend mot pour mot un texte de plus de "
           "9 caractères de l'exemple de la consigne (un sujet de vélo). « Chiffres absents de la source » compte les nombres (hors entiers de 0 à 10) qui ne "
           "figurent pas dans le texte source, ni ×100 ni ÷100 : ce sont des chiffres inventés, mal recopiés ou "
           "calculés par le modèle. « Mots pleins absents » est un indicateur grossier d'ajouts (mots de six "
           "lettres ou plus, comparés sur leurs six premières lettres) : une reformulation légitime l'augmente "
           "aussi.", "", "## Détail par demande", ""]
    md += ["| Demande | Sorte | Mode | " + " | ".join(modeles) + " |", "|---|---|---|" + "---|" * len(modeles)]
    for i, dm in demandes.items():
        cases = []
        for m in modeles:
            l = next((x for x in lignes[m] if x["id"] == i), None)
            if l is None:
                cases.append("–")
                continue
            etat = ("valide" if l["json_valide"] == "True" and l["rendu_ok"] == "True"
                    else ("hors schéma" if l["rendu_ok"] == "True" else "échec"))
            info = f"{etat} {float(l['secondes']):.0f} s"
            if l.get("chiffres_inventes"):
                info += f", inventés {_pct(_f(l['chiffres_inventes']))}"
            if "limite de jetons" in l["erreur"]:
                info += ", boucle"
            cases.append(info)
        md.append(f"| {i} | {dm['sorte']} | {dm['mode']} | " + " | ".join(cases) + " |")
    md += ["", "« valide » : JSON conforme et fichiers produits (ce qui ne dit rien de la justesse du contenu) ; "
           "« hors schéma » : fichiers produits mais un texte trop long ou trop d'éléments ; « échec » : aucun "
           "fichier. « inventés » : part des nombres absents de la source (mesure automatique).", ""]
    md += ["", "## Relecture manuelle (demandes « texte fourni »)", "",
           "Les mesures automatiques ne voient pas un chiffre de la source mal attribué ni un calcul faux "
           "fait avec des chiffres justes. Chaque sortie a donc été relue. Règle : ❌ si un lecteur repart "
           "avec une information fausse (chiffre, calcul, graphique trompeur, contenu de l'exemple) ; 🟡 si "
           "c'est juste mais incomplet ou avec un ajout sans conséquence ; ✅ sinon.", "",
           "| Modèle | Demande | Note | Justification |", "|---|---|---|---|"]
    md += [f"| {r['modele']} | {r['id']} | {r['note']} | {r['justification']} |" for r in rel]
    (RACINE / "RESULTATS.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
