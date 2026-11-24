"""Corrections mécaniques du JSON produit par le modèle, avant le rendu.

Uniquement des réparations de forme, jamais de contenu : la liste des
corrections est renvoyée pour que l'utilisateur (et le banc d'essai) voie ce
qui a été modifié.
"""
from __future__ import annotations

import re

_SOULIGNE = re.compile(r"^_+(.*?)_+$", re.S)


def _texte(v):
    if isinstance(v, str):
        m = _SOULIGNE.match(v.strip())
        v = m.group(1) if m else v.strip()
        if v.lower() in ("null", "none", "n/a"):
            return None
    return v


def nettoyer(d: dict) -> tuple[dict, list[str]]:
    corr: list[str] = []
    if not isinstance(d, dict):
        return d, corr
    if d.get("type") == "document":
        for s in d.get("sections", []):
            for b in s.get("blocs", []):
                if b.get("type") == "tableau":
                    _tableau(b, corr)
                if b.get("type") == "graphique":
                    _graphique(b, corr)
                if b.get("type") == "liste":
                    _liste(b, corr)
        _titres_doublons(d.get("sections", []), corr)
    elif d.get("type") == "presentation":
        for dia in d.get("diapositives", []):
            if isinstance(dia.get("image"), dict) and dia["image"].get("type") == "graphique":
                _graphique(dia["image"], corr)
    elif d.get("type") == "classeur":
        for f in d.get("feuilles", []):
            _feuille(f, corr)
    return d, corr


_NUMERO = re.compile(r"^\s*(\d+[.)]|[-•*])\s+")


def _liste(b, corr):
    """« 1. Scène » dans une liste : le numéro est retiré et la liste devient ordonnée."""
    els = b.get("elements", [])
    if els and all(_NUMERO.match(e) for e in els):
        numerotee = all(re.match(r"^\s*\d", e) for e in els)
        b["elements"] = [_NUMERO.sub("", e, count=1) for e in els]
        if numerotee:
            b["ordonnee"] = True
        corr.append("liste : numéros ou puces écrits dans le texte retirés")


def _tableau(b, corr):
    n = len(b.get("entetes", []))
    for i, l in enumerate(b.get("lignes", [])):
        if len(l) != n:
            corr.append(f"tableau « {b['entetes'][0] if n else ''} » : ligne {i + 1} ramenée à {n} cellules")
            b["lignes"][i] = (list(l) + [""] * n)[:n]


def _graphique(g, corr):
    n = len(g.get("etiquettes", []))
    for s in g.get("series", []):
        if len(s.get("valeurs", [])) != n:
            corr.append(f"graphique « {g.get('titre', '')} » : série {s.get('nom')!r} ramenée à {n} valeurs")
            s["valeurs"] = (list(s.get("valeurs", [])) + [0] * n)[:n]


def _titres_doublons(sections, corr):
    vus = {}
    for s in sections:
        t = s.get("titre", "")
        if t in vus:
            vus[t] += 1
            corr.append(f"titre de section répété : « {t} »")
        else:
            vus[t] = 1


def _feuille(f, corr):
    cols = f.get("colonnes", [])
    noms = [c.get("nom", "") for c in cols]
    for c in cols:
        fo = c.get("formule")
        if isinstance(fo, str):
            # « C{Quantité} » ou « {Prix}2 » : le modèle mélange nom de colonne et référence A1.
            propre = re.sub(r"\b[A-Z]{1,2}\$?(?=\{)", "", fo)
            propre = re.sub(r"(\{[^{}]+\})\$?\d+", r"\1", propre)
            if propre != fo:
                corr.append(f"feuille « {f.get('nom')} » : formule {fo!r} corrigée en {propre!r}")
                c["formule"] = fo = propre
        if fo is not None and (not isinstance(fo, str) or not re.search(r"\{[^{}]+\}|\[[^\[\]]+\]", fo)):
            corr.append(f"feuille « {f.get('nom')} » : formule sans référence de colonne retirée ({fo!r})")
            c.pop("formule")
    lignes = []
    for l in f.get("lignes", []):
        l = [_texte(v) for v in l]
        if [str(v).strip().lower() for v in l[:len(noms)]] == [n.strip().lower() for n in noms]:
            corr.append(f"feuille « {f.get('nom')} » : ligne d'en-têtes recopiée dans les données, retirée")
            continue
        if all(v in (None, "") for v in l):
            continue
        if len(l) != len(noms):
            corr.append(f"feuille « {f.get('nom')} » : ligne ramenée à {len(noms)} cellules")
            l = (l + [None] * len(noms))[:len(noms)]
        lignes.append(l)
    f["lignes"] = lignes or [[None] * len(noms)]
    connus = {n.strip().lower() for n in noms}
    tot = [t for t in f.get("totaux", []) if t.get("colonne", "").strip().lower() in connus]
    if len(tot) != len(f.get("totaux", [])):
        corr.append(f"feuille « {f.get('nom')} » : total sur une colonne inconnue retiré")
    if "totaux" in f:
        f["totaux"] = tot
    g = f.get("graphique")
    if g and not ({g.get("etiquettes", "").strip().lower(), *[v.strip().lower() for v in g.get("valeurs", [])]} <= connus):
        corr.append(f"feuille « {f.get('nom')} » : graphique sur une colonne inconnue retiré")
        f.pop("graphique")
