"""Schéma JSON commun aux trois sortes de livrables.

Le petit modèle ne fabrique jamais de fichier : il remplit ce schéma sous
génération contrainte, puis un moteur de rendu déterministe produit les
fichiers. Les limites (maxItems, maxLength) servent à la génération : elles
empêchent un petit modèle de boucler indéfiniment.
"""
from __future__ import annotations

import copy

import jsonschema

TXT = {"type": "string", "maxLength": 1200}
COURT = {"type": "string", "maxLength": 160}


def _liste(item, maxi=12, mini=0):
    return {"type": "array", "items": item, "minItems": mini, "maxItems": maxi}


# --- Images -----------------------------------------------------------------
GRAPHIQUE = {
    "type": "object",
    "properties": {
        "type": {"const": "graphique"},
        "forme": {"enum": ["barres", "courbes", "camembert"]},
        "titre": COURT,
        "etiquettes": _liste(COURT, 12, 1),
        "series": _liste({
            "type": "object",
            "properties": {"nom": COURT, "valeurs": _liste({"type": "number"}, 12, 1)},
            "required": ["nom", "valeurs"],
            "additionalProperties": False,
        }, 4, 1),
        "legende": COURT,
    },
    "required": ["type", "forme", "titre", "etiquettes", "series"],
    "additionalProperties": False,
}
SCHEMA_DIAGRAMME = {
    "type": "object",
    "properties": {
        "type": {"const": "schema"},
        "langage": {"enum": ["graphviz", "mermaid"]},
        "code": {"type": "string", "maxLength": 1500},
        "legende": COURT,
    },
    "required": ["type", "langage", "code"],
    "additionalProperties": False,
}
# Variante structurée, utilisée pour la génération : un petit modèle qui écrit
# du code Graphviz libre peut boucler sans fin (ajout d'arêtes) ; une liste de
# liens est bornée par la grammaire (maxItems) et l'outil écrit le code DOT.
SCHEMA_LIENS = {
    "type": "object",
    "properties": {
        "type": {"const": "schema"},
        "sens": {"enum": ["haut-bas", "gauche-droite"]},
        "liens": _liste({
            "type": "object",
            "properties": {"de": COURT, "vers": COURT, "etiquette": COURT},
            "required": ["de", "vers"],
            "additionalProperties": False,
        }, 12, 1),
        "legende": COURT,
    },
    "required": ["type", "liens"],
    "additionalProperties": False,
}
ICONE = {
    "type": "object",
    "properties": {"type": {"const": "icone"}, "mot_cle": COURT, "legende": COURT},
    "required": ["type", "mot_cle"],
    "additionalProperties": False,
}
IMAGE_FICHIER = {
    "type": "object",
    "properties": {"type": {"const": "image"}, "chemin": COURT, "legende": COURT},
    "required": ["type", "chemin"],
    "additionalProperties": False,
}

# --- Blocs de document --------------------------------------------------------
PARAGRAPHE = {
    "type": "object",
    "properties": {"type": {"const": "paragraphe"}, "texte": TXT},
    "required": ["type", "texte"],
    "additionalProperties": False,
}
LISTE = {
    "type": "object",
    "properties": {
        "type": {"const": "liste"},
        "ordonnee": {"type": "boolean"},
        "elements": _liste(TXT, 12, 1),
    },
    "required": ["type", "elements"],
    "additionalProperties": False,
}
TABLEAU = {
    "type": "object",
    "properties": {
        "type": {"const": "tableau"},
        "entetes": _liste(COURT, 8, 1),
        "lignes": _liste(_liste({"type": ["string", "number"]}, 8, 1), 20, 1),
        "legende": COURT,
    },
    "required": ["type", "entetes", "lignes"],
    "additionalProperties": False,
}
CITATION = {
    "type": "object",
    "properties": {"type": {"const": "citation"}, "texte": TXT, "auteur": COURT},
    "required": ["type", "texte"],
    "additionalProperties": False,
}
IMAGES = [GRAPHIQUE, SCHEMA_DIAGRAMME, SCHEMA_LIENS, ICONE, IMAGE_FICHIER]
BLOC = {"anyOf": [PARAGRAPHE, LISTE, TABLEAU, CITATION] + IMAGES}

SECTION = {
    "type": "object",
    "properties": {"titre": COURT, "blocs": _liste(BLOC, 8, 1)},
    "required": ["titre", "blocs"],
    "additionalProperties": False,
}
DOCUMENT = {
    "type": "object",
    "properties": {
        "type": {"const": "document"},
        "titre": COURT,
        "sous_titre": COURT,
        "sections": _liste(SECTION, 10, 1),
    },
    "required": ["type", "titre", "sections"],
    "additionalProperties": False,
}

# --- Présentation -------------------------------------------------------------
_POINTS = _liste(COURT, 6, 1)
_NOTES = {"type": "string", "maxLength": 600}


def _diapo(mise_en_page, props, requis):
    p = {"mise_en_page": {"const": mise_en_page}, **props, "notes": _NOTES}
    return {"type": "object", "properties": p,
            "required": ["mise_en_page", *requis], "additionalProperties": False}


COLONNE = {
    "type": "object",
    "properties": {"titre": COURT, "points": _POINTS},
    "required": ["titre", "points"],
    "additionalProperties": False,
}
DIAPOSITIVE = {"anyOf": [
    _diapo("titre", {"titre": COURT, "sous_titre": COURT}, ["titre"]),
    _diapo("points", {"titre": COURT, "points": _POINTS}, ["titre", "points"]),
    _diapo("deux_colonnes", {"titre": COURT, "gauche": COLONNE, "droite": COLONNE},
           ["titre", "gauche", "droite"]),
    _diapo("image_texte", {"titre": COURT, "image": {"anyOf": IMAGES}, "points": _POINTS},
           ["titre", "image", "points"]),
    _diapo("chiffre_cle", {"titre": COURT, "chiffre": {"type": "string", "maxLength": 24},
                           "legende": COURT}, ["titre", "chiffre", "legende"]),
    _diapo("citation", {"texte": TXT, "auteur": COURT}, ["texte"]),
]}
PRESENTATION = {
    "type": "object",
    "properties": {
        "type": {"const": "presentation"},
        "titre": COURT,
        "sous_titre": COURT,
        "diapositives": _liste(DIAPOSITIVE, 15, 1),
    },
    "required": ["type", "titre", "diapositives"],
    "additionalProperties": False,
}
MISES_EN_PAGE = ["titre", "points", "deux_colonnes", "image_texte", "chiffre_cle", "citation"]

# --- Classeur -------------------------------------------------------------------
# Les formules sont écrites avec des NOMS de colonnes ({Prix} * {Quantité}) ;
# le moteur de rendu les traduit en références A1. Les petits modèles se
# trompent souvent de lettre de colonne, beaucoup moins de nom.
COLONNE_TABLEUR = {
    "type": "object",
    "properties": {
        "nom": COURT,
        "format": {"enum": ["texte", "nombre", "monnaie", "pourcentage", "date"]},
        "formule": {"type": "string", "maxLength": 200},
    },
    "required": ["nom", "format"],
    "additionalProperties": False,
}
FEUILLE = {
    "type": "object",
    "properties": {
        "nom": {"type": "string", "maxLength": 31},
        "colonnes": _liste(COLONNE_TABLEUR, 10, 1),
        "lignes": _liste(_liste({"type": ["string", "number", "null"]}, 10, 1), 40, 1),
        "totaux": _liste({
            "type": "object",
            "properties": {
                "colonne": COURT,
                "fonction": {"enum": ["SOMME", "MOYENNE", "MIN", "MAX", "NB"]},
            },
            "required": ["colonne", "fonction"],
            "additionalProperties": False,
        }, 10),
        "graphique": {
            "type": "object",
            "properties": {
                "forme": {"enum": ["barres", "courbes", "camembert"]},
                "titre": COURT,
                "etiquettes": COURT,
                "valeurs": _liste(COURT, 4, 1),
            },
            "required": ["forme", "titre", "etiquettes", "valeurs"],
            "additionalProperties": False,
        },
    },
    "required": ["nom", "colonnes", "lignes"],
    "additionalProperties": False,
}
CLASSEUR = {
    "type": "object",
    "properties": {
        "type": {"const": "classeur"},
        "titre": COURT,
        "feuilles": _liste(FEUILLE, 5, 1),
    },
    "required": ["type", "titre", "feuilles"],
    "additionalProperties": False,
}

LIVRABLE = {"anyOf": [DOCUMENT, PRESENTATION, CLASSEUR]}
SCHEMAS = {"document": DOCUMENT, "presentation": PRESENTATION, "classeur": CLASSEUR}

# --- Mode « sujet seul » : plan, puis contenu partie par partie -----------------
PLAN = {
    "type": "object",
    "properties": {
        "titre": COURT,
        "parties": _liste({
            "type": "object",
            "properties": {"titre": COURT, "idee": {"type": "string", "maxLength": 300}},
            "required": ["titre", "idee"],
            "additionalProperties": False,
        }, 10, 2),
    },
    "required": ["titre", "parties"],
    "additionalProperties": False,
}
# --- Consigne en deux temps : faits extraits du texte, puis mise en forme -----------
FAITS = {
    "type": "object",
    "properties": {
        "faits": _liste({
            "type": "object",
            "properties": {"objet": COURT, "information": {"type": "string", "maxLength": 400},
                           "chiffres": _liste(COURT, 6)},
            "required": ["objet", "information", "chiffres"],
            "additionalProperties": False,
        }, 30, 1),
    },
    "required": ["faits"],
    "additionalProperties": False,
}
PARTIE = {"document": SECTION, "presentation": DIAPOSITIVE, "classeur": FEUILLE}


def _images_autorisees(images: bool, fichiers: list[str] | None) -> list[dict]:
    """Blocs image proposés au modèle. Les fichiers de l'utilisateur sont une
    liste fermée (enum) : le modèle ne peut pas inventer de chemin."""
    out = [GRAPHIQUE, SCHEMA_LIENS, ICONE] if images else []
    if fichiers:
        f = copy.deepcopy(IMAGE_FICHIER)
        f["properties"]["chemin"] = {"enum": list(fichiers)}
        out.append(f)
    return out


def _sans_maxlength(s):
    """Retire maxLength du schéma de génération.

    Le convertisseur de llama-cpp-python traduit maxLength en optionnels
    imbriqués, un niveau par caractère : avec 1 200 caractères, llama.cpp
    refuse la grammaire (« grammar recursion depth limit exceeded (max 256) »).
    La longueur des textes est donc tenue par la consigne et max_tokens, et
    vérifiée après coup par valider(). maxItems (≤ 40) reste."""
    if isinstance(s, dict):
        return {k: _sans_maxlength(v) for k, v in s.items() if k != "maxLength"}
    if isinstance(s, list):
        return [_sans_maxlength(v) for v in s]
    return s


def schema_generation(sorte: str, images: bool = True, fichiers: list[str] | None = None,
                      partie: bool = False) -> dict:
    """Schéma passé au modèle (`partie=True` : une section, une diapositive ou une
    feuille, pour le mode « sujet seul »)."""
    imgs = _images_autorisees(images, fichiers)
    s = copy.deepcopy(SCHEMAS[sorte])
    if sorte == "document":
        s["properties"]["sections"]["items"]["properties"]["blocs"]["items"] = {
            "anyOf": [PARAGRAPHE, LISTE, TABLEAU, CITATION] + imgs}
    if sorte == "presentation":
        dias = copy.deepcopy(DIAPOSITIVE["anyOf"])
        if imgs:
            for d in dias:
                if d["properties"]["mise_en_page"]["const"] == "image_texte":
                    d["properties"]["image"] = {"anyOf": imgs}
        else:
            dias = [d for d in dias if d["properties"]["mise_en_page"]["const"] != "image_texte"]
        s["properties"]["diapositives"]["items"] = {"anyOf": dias}
    if partie:
        cle = {"document": "sections", "presentation": "diapositives", "classeur": "feuilles"}[sorte]
        s = s["properties"][cle]["items"]
    return _sans_maxlength(s)


def valider(donnees: dict) -> list[str]:
    """Renvoie la liste des erreurs (vide si le JSON est conforme)."""
    sorte = donnees.get("type") if isinstance(donnees, dict) else None
    if sorte not in SCHEMAS:
        return [f"type inconnu : {sorte!r} (attendu : {', '.join(SCHEMAS)})"]
    v = jsonschema.Draft202012Validator(SCHEMAS[sorte])
    erreurs = [f"{'/'.join(map(str, e.absolute_path)) or '(racine)'} : {e.message[:200]}"
               for e in v.iter_errors(donnees)]
    return erreurs + _verifier_coherence(donnees)


def _verifier_coherence(d: dict) -> list[str]:
    """Contrôles que le schéma ne sait pas exprimer."""
    err = []

    def graph(g, ou):
        n = len(g.get("etiquettes", []))
        for s in g.get("series", []):
            if len(s.get("valeurs", [])) != n:
                err.append(f"{ou} : la série {s.get('nom')!r} a {len(s.get('valeurs', []))} valeurs pour {n} étiquettes")

    if d["type"] == "document":
        for i, sec in enumerate(d.get("sections", [])):
            for j, b in enumerate(sec.get("blocs", [])):
                if b.get("type") == "graphique":
                    graph(b, f"sections/{i}/blocs/{j}")
                if b.get("type") == "tableau":
                    n = len(b.get("entetes", []))
                    for k, ligne in enumerate(b.get("lignes", [])):
                        if len(ligne) != n:
                            err.append(f"sections/{i}/blocs/{j}/lignes/{k} : {len(ligne)} cellules pour {n} en-têtes")
    elif d["type"] == "presentation":
        for i, dia in enumerate(d.get("diapositives", [])):
            if isinstance(dia.get("image"), dict) and dia["image"].get("type") == "graphique":
                graph(dia["image"], f"diapositives/{i}/image")
    elif d["type"] == "classeur":
        for i, f in enumerate(d.get("feuilles", [])):
            noms = [c["nom"] for c in f.get("colonnes", [])]
            for t in f.get("totaux", []):
                if t["colonne"] not in noms:
                    err.append(f"feuilles/{i}/totaux : colonne inconnue {t['colonne']!r}")
            g = f.get("graphique")
            if g:
                for c in [g["etiquettes"], *g["valeurs"]]:
                    if c not in noms:
                        err.append(f"feuilles/{i}/graphique : colonne inconnue {c!r}")
    return err
