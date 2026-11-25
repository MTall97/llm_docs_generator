"""Banc d'essai : 15 demandes en français, un modèle par exécution.

  python banc/lancer.py modeles/qwen2.5-1.5b-instruct-q4_k_m.gguf
  python banc/rapport.py            # → banc/RESULTATS.md

Mesures (automatiques, donc approximatives ; voir README) :
- json_valide : JSON analysable et conforme au schéma (structure) ;
- corrections : incohérences réparées par le nettoyage (lignes trop courtes…) ;
- rendu_ok : les fichiers des formats par défaut ont été produits ;
- chiffres_inventes : part des nombres du résultat absents du texte source ;
- chiffres_repris : part des nombres du texte source présents dans le résultat ;
- mots_hors_source : part des mots pleins du résultat absents du texte source ;
- recopie_exemple : textes repris mot pour mot de l'exemple de la consigne ;
- secondes, jetons produits, jetons/s, mémoire maximale du processus.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import resource
import sys
import time
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from docgen.generation import EXEMPLES, Generateur  # noqa: E402
from docgen.rendu import rendre  # noqa: E402
from docgen.schema import valider  # noqa: E402

CLES_TECHNIQUES = {"type", "mise_en_page", "format", "forme", "fonction", "langage", "sens", "formule",
                   "chemin", "ordonnee"}
_NOMBRE = re.compile(r"\d{1,3}(?:[   ]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?")


def _textes_et_nombres(d, textes, nombres):
    if isinstance(d, dict):
        for k, v in d.items():
            if k not in CLES_TECHNIQUES:
                _textes_et_nombres(v, textes, nombres)
    elif isinstance(d, list):
        for v in d:
            _textes_et_nombres(v, textes, nombres)
    elif isinstance(d, bool) or d is None:
        pass
    elif isinstance(d, (int, float)):
        nombres.append(float(d))
    elif isinstance(d, str):
        textes.append(d)


def nombres_du_texte(t: str) -> list[float]:
    out = []
    for m in _NOMBRE.findall(t):
        s = re.sub(r"[   ]", "", m).replace(",", ".")
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def _significatif(n: float) -> bool:
    # On ignore les petits entiers (numéros d'étape, « 2 classes »…) : trop ambigus.
    return not (float(n).is_integer() and 0 <= n <= 10)


def _equivalents(n: float) -> set:
    return {round(n, 4), round(n * 100, 4), round(n / 100, 6)}  # 0,52 ≈ 52 %


def _mots(t: str) -> set[str]:
    t = "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")
    return {m[:6] for m in re.findall(r"[a-z]{6,}", t)}  # racine grossière : 6 premières lettres


def fidelite(source: str, d: dict) -> dict:
    textes, nombres = [], []
    _textes_et_nombres(d, textes, nombres)
    for t in textes:
        nombres += nombres_du_texte(t)
    src = [n for n in nombres_du_texte(source) if _significatif(n)]
    src_eq = set().union(*(_equivalents(n) for n in src)) if src else set()
    sortie = [n for n in nombres if _significatif(n)]
    inventes = [n for n in sortie if round(n, 4) not in src_eq]
    repris = [n for n in set(src) if any(_equivalents(n) & {round(m, 4), round(m, 6)} for m in sortie)]
    mots_src, mots_out = _mots(source), _mots(" ".join(textes))
    return {
        "chiffres_inventes": round(len(inventes) / len(sortie), 3) if sortie else 0.0,
        "exemples_inventes": " ; ".join(sorted({f"{n:g}" for n in inventes})[:6]),
        "chiffres_repris": round(len(repris) / len(set(src)), 3) if src else None,
        "mots_hors_source": round(len(mots_out - mots_src) / len(mots_out), 3) if mots_out else None,
    }


def _chaines(d):
    t, n = [], []
    _textes_et_nombres(d, t, n)
    # > 9 caractères : on ignore les mots génériques (« Quantité », « Total », « Étapes »)
    return {x.strip().lower() for x in t if len(x.strip()) > 9}


CHAINES_EXEMPLES = {s: _chaines(e) for s, e in EXEMPLES.items()}


def recopie_exemple(sorte: str, d: dict) -> int:
    """Nombre de textes repris mot pour mot de l'exemple donné dans la consigne."""
    return len(_chaines(d) & CHAINES_EXEMPLES[sorte])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modele")
    ap.add_argument("--ids", nargs="*", help="sous-ensemble de demandes")
    ap.add_argument("--sans-exemple", action="store_true", help="pas d'exemple JSON dans la consigne")
    ap.add_argument("--deux-temps", action="store_true", help="extraire les faits puis mettre en forme")
    a = ap.parse_args()
    nom = Path(a.modele).stem.replace("-instruct-q4_k_m", "").replace("-instruct-2507-q4_k_m", "-2507") + ("-sans-exemple" if a.sans_exemple else "") + ("-deux-temps" if a.deux_temps else "")
    dossier = RACINE / "banc" / "resultats" / nom
    dossier.mkdir(parents=True, exist_ok=True)
    demandes = json.loads((RACINE / "banc" / "demandes.json").read_text(encoding="utf-8"))
    if a.ids:
        demandes = [d for d in demandes if d["id"] in a.ids]
    t0 = time.perf_counter()
    g = Generateur(a.modele, n_ctx=8192, n_threads=4, exemple=not a.sans_exemple)
    chargement = time.perf_counter() - t0
    lignes = []
    for dm in demandes:
        print(f"[{nom}] {dm['id']} …", flush=True)
        ton = dm.get("ton", "formel")
        if dm["mode"] == "texte":
            r = g.depuis_texte(dm["texte"], dm["sorte"], dm.get("consigne", ""), ton, deux_temps=a.deux_temps)
            if a.deux_temps and r.etapes:
                (dossier / f"{dm['id']}_faits.json").write_text(
                    json.dumps(r.etapes[0]["faits"], ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            p = g.plan(dm["sujet"], dm["sorte"], 4, ton)
            if p.donnees is None:
                r = p
            else:
                r = g.rediger(p.donnees, dm["sorte"], ton)
                r.secondes += p.secondes
                r.jetons_sortie += p.jetons_sortie
                (dossier / f"{dm['id']}_plan.json").write_text(json.dumps(p.donnees, ensure_ascii=False, indent=1),
                                                               encoding="utf-8")
        ligne = {"modele": nom, "id": dm["id"], "sorte": dm["sorte"], "mode": dm["mode"],
                 "secondes": round(r.secondes, 1), "jetons_sortie": r.jetons_sortie,
                 "jetons_par_s": round(r.jetons_sortie / r.secondes, 1) if r.secondes else 0,
                 "json_valide": False, "erreurs_schema": "", "corrections": len(r.corrections),
                 "rendu_ok": False, "erreur": r.erreur}
        if r.donnees is not None:
            (dossier / f"{dm['id']}.json").write_text(json.dumps(r.donnees, ensure_ascii=False, indent=1),
                                                      encoding="utf-8")
            err = valider(r.donnees)
            structure = [e for e in err if "cellules pour" not in e and "la série" not in e
                         and "colonne inconnue" not in e]
            ligne["json_valide"] = not structure
            ligne["erreurs_schema"] = " | ".join(structure)[:300]
            try:
                rendre(r.donnees, dossier / dm["id"], verifier=False)
                ligne["rendu_ok"] = True
            except Exception as e:  # noqa: BLE001
                ligne["erreur"] += f" rendu : {type(e).__name__}: {e}"[:200]
            ligne["recopie_exemple"] = recopie_exemple(dm["sorte"], r.donnees)
            if dm["mode"] == "texte":
                ligne.update(fidelite(dm["texte"], r.donnees))
        if r.corrections:
            (dossier / f"{dm['id']}_corrections.txt").write_text("\n".join(r.corrections), encoding="utf-8")
        lignes.append(ligne)
        print(f"   {ligne['secondes']} s, valide={ligne['json_valide']}, rendu={ligne['rendu_ok']}, "
              f"inventés={ligne.get('chiffres_inventes')}", flush=True)
    memoire = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    champs = ["modele", "id", "sorte", "mode", "secondes", "jetons_sortie", "jetons_par_s", "json_valide",
              "erreurs_schema", "corrections", "rendu_ok", "recopie_exemple", "chiffres_inventes", "exemples_inventes",
              "chiffres_repris", "mots_hors_source", "erreur"]
    with open(dossier / "mesures.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, champs, extrasaction="ignore")
        w.writeheader()
        w.writerows(lignes)
    (dossier / "machine.json").write_text(json.dumps({
        "modele": nom, "fichier_mo": round(Path(a.modele).stat().st_size / 1e6),
        "chargement_s": round(chargement, 1), "memoire_max_mo": round(memoire), "threads": 4},
        indent=1), encoding="utf-8")
    print(f"mémoire max {memoire:.0f} Mo")


if __name__ == "__main__":
    main()
