"""Le petit modèle remplit le schéma JSON sous génération contrainte.

llama-cpp-python convertit le schéma JSON en grammaire (GBNF) : à chaque
jeton, seuls les jetons qui gardent le JSON conforme sont permis. Le JSON
produit est donc toujours analysable et respecte la structure ; le contenu
(fidélité, pertinence) dépend en revanche entièrement du modèle.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .nettoyage import nettoyer
from .schema import FAITS, PLAN, _sans_maxlength, schema_generation

TONS = {
    "formel": "Ton formel et professionnel, vouvoiement, phrases complètes.",
    "pedagogique": "Ton pédagogique : explique simplement, définis les termes, donne des exemples.",
    "convivial": "Ton convivial et direct, phrases courtes.",
    "concis": "Style télégraphique et concis : phrases très courtes, l'essentiel seulement.",
}

CONSIGNES = {
    "document": (
        "Produis un DOCUMENT : un titre et 2 à 5 sections aux titres tous différents. Chaque section contient "
        "des blocs : paragraphe, liste, tableau (chaque ligne a autant de cellules que d'en-têtes), "
        "citation{images}. Ne répète pas la même information dans deux blocs."),
    "presentation": (
        "Produis une PRÉSENTATION de 4 à 8 diapositives. Mises en page possibles : titre ; points "
        "(3 à 5 puces de moins de 12 mots) ; deux_colonnes (deux listes à comparer) ; chiffre_cle "
        "(un seul nombre marquant et sa légende) ; citation{images}. Varie les mises en page. "
        "Un titre de diapositive fait moins de 8 mots."),
    "classeur": (
        "Produis un CLASSEUR : des feuilles avec des colonnes (nom + format : texte, nombre, monnaie, "
        "pourcentage, date) et des lignes de valeurs (une valeur par colonne, nombres écrits comme des "
        "nombres JSON, sans unité). Ne calcule JAMAIS toi-même "
        "un total ou un produit : pour une colonne calculée, donne une « formule » avec les noms de colonnes "
        "entre accolades, par exemple \"{{Prix}} * {{Quantité}}\", et laisse cette colonne vide (null) dans les lignes. "
        "N'ajoute une formule que si un calcul est vraiment demandé. "
        "Pour les totaux, utilise « totaux » (colonne + fonction SOMME, MOYENNE, MIN, MAX ou NB). "
        "« graphique » est facultatif : etiquettes = nom d'une colonne, valeurs = noms de colonnes."),
}
# Un exemple court par sorte, sur un sujet volontairement éloigné des demandes,
# pour montrer la forme attendue sans fournir de contenu à recopier.
EXEMPLES = {
    "document": {"type": "document", "titre": "Entretien d'un vélo", "sections": [
        {"titre": "Matériel", "blocs": [
            {"type": "paragraphe", "texte": "Un entretien mensuel suffit pour un usage quotidien."},
            {"type": "tableau", "entetes": ["Outil", "Usage"],
             "lignes": [["Pompe", "Gonfler les pneus"], ["Huile", "Graisser la chaîne"]]}]},
        {"titre": "Étapes", "blocs": [
            {"type": "liste", "ordonnee": True, "elements": ["Nettoyer la chaîne", "Vérifier les freins"]}]}]},
    "presentation": {"type": "presentation", "titre": "Entretien d'un vélo", "diapositives": [
        {"mise_en_page": "titre", "titre": "Entretien d'un vélo", "sous_titre": "Atelier du samedi"},
        {"mise_en_page": "points", "titre": "Chaque mois", "points": ["Graisser la chaîne", "Gonfler les pneus"]},
        {"mise_en_page": "chiffre_cle", "titre": "Pression", "chiffre": "4 bars", "legende": "pour un vélo de ville"}]},
    "classeur": {"type": "classeur", "titre": "Pièces de vélo", "feuilles": [
        {"nom": "Achats", "colonnes": [
            {"nom": "Pièce", "format": "texte"}, {"nom": "Prix", "format": "monnaie"},
            {"nom": "Quantité", "format": "nombre"},
            {"nom": "Total", "format": "monnaie", "formule": "{Prix} * {Quantité}"}],
         "lignes": [["Chambre à air", 6.5, 2, None], ["Patins", 9, 4, None]],
         "totaux": [{"colonne": "Total", "fonction": "SOMME"}]}]},
}

IMAGES = {
    "document": ", et si c'est utile : graphique (barres, courbes ou camembert, seulement avec des chiffres "
                "de la source ; une valeur par étiquette), schema (liste de liens de → vers entre les "
                "vraies étapes ou entités du texte, 12 au plus), icone (un mot-clé du sujet)",
    "presentation": " ; image_texte (une image et des puces ; l'image est un graphique fait avec des chiffres "
                    "de la source, une valeur par étiquette, un schéma (liens de → vers) ou une icône)",
}


@dataclass
class Resultat:
    donnees: dict | None
    texte_brut: str
    secondes: float
    jetons_entree: int = 0
    jetons_sortie: int = 0
    erreur: str = ""
    etapes: list = field(default_factory=list)
    corrections: list = field(default_factory=list)


class Generateur:
    def __init__(self, chemin_modele: str | Path, n_ctx: int = 8192, n_threads: int | None = None,
                 temperature: float = 0.2, graine: int = 42, exemple: bool = True):
        from llama_cpp import Llama  # import tardif : les moteurs de rendu n'en dépendent pas
        self.chemin = Path(chemin_modele)
        self.llm = Llama(model_path=str(self.chemin), n_ctx=n_ctx, n_threads=n_threads or os.cpu_count(),
                         seed=graine, verbose=False)
        self.temperature = temperature
        self.exemple = exemple  # False : pas d'exemple JSON dans la consigne (le 0.5B le recopie)

    def _appel(self, systeme: str, utilisateur: str, schema: dict, max_jetons: int) -> Resultat:
        t0 = time.perf_counter()
        r = self.llm.create_chat_completion(
            messages=[{"role": "system", "content": systeme}, {"role": "user", "content": utilisateur}],
            response_format={"type": "json_object", "schema": schema},
            temperature=self.temperature, max_tokens=max_jetons, repeat_penalty=1.05)
        dt = time.perf_counter() - t0
        brut = r["choices"][0]["message"]["content"] or ""
        u = r.get("usage", {})
        res = Resultat(None, brut, dt, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
        try:
            res.donnees = json.loads(brut)
        except json.JSONDecodeError as e:
            fin = r["choices"][0].get("finish_reason")
            res.erreur = f"JSON incomplet ({'limite de jetons atteinte' if fin == 'length' else e})"
        return res

    def _systeme(self, sorte, ton, images, fichiers):
        img = IMAGES.get(sorte, "") if images else ""
        if fichiers:
            img += (", « image » pour placer une image fournie par l'utilisateur "
                    f"(chemin parmi : {', '.join(fichiers)}) avec une légende")
        consigne = ("Tu rédiges en français et tu réponds uniquement en JSON. "
                    + CONSIGNES[sorte].format(images=img) + " " + TONS.get(ton, TONS["formel"]))
        if getattr(self, "exemple", True):
            consigne += ("\nExemple de forme (sujet sans rapport, ne pas recopier) : "
                         + json.dumps(EXEMPLES[sorte], ensure_ascii=False))
        return consigne

    # -- Mode 1 : transformer un texte fourni ---------------------------------------------
    def extraire_faits(self, texte: str, max_jetons: int = 2000) -> Resultat:
        """Étape 1 de la consigne en deux temps : liste des faits, chiffres recopiés tels quels."""
        systeme = ("Tu réponds uniquement en JSON, en français. Lis le texte et liste TOUS ses faits, un par "
                   "élément, dans l'ordre du texte. « objet » : de qui ou de quoi parle le fait. « information » : "
                   "le fait en une phrase courte. « chiffres » : chaque nombre du fait recopié EXACTEMENT, avec son "
                   "unité et ce qu'il compte (par exemple « 31 euros par personne et par nuit », « 64 personnes »). "
                   "Ne déduis rien, ne calcule rien, n'ajoute rien.")
        return self._appel(systeme, f"Texte :\n\"\"\"\n{texte.strip()}\n\"\"\"", _sans_maxlength(FAITS), max_jetons)

    @staticmethod
    def faits_en_texte(faits: dict) -> str:
        lignes = []
        for i, f in enumerate(faits.get("faits", []), 1):
            ch = f" [chiffres : {' ; '.join(f['chiffres'])}]" if f.get("chiffres") else ""
            lignes.append(f"{i}. {f['objet']} : {f['information']}{ch}")
        return "\n".join(lignes)

    def depuis_texte(self, texte: str, sorte: str, consigne: str = "", ton: str = "formel",
                     images: bool = True, fichiers: list[str] | None = None, max_jetons: int = 3000,
                     deux_temps: bool = False) -> Resultat:
        """`deux_temps=True` : extraire d'abord les faits (étape 1), puis mettre en forme
        cette liste au lieu du texte brut (étape 2)."""
        faits = None
        if deux_temps:
            rf = self.extraire_faits(texte)
            if rf.donnees is None:
                return rf
            faits = rf
            source = ("Faits extraits du texte source (seules informations à utiliser) :\n"
                      + self.faits_en_texte(rf.donnees))
        else:
            source = f"Texte source :\n\"\"\"\n{texte.strip()}\n\"\"\""
        systeme = self._systeme(sorte, ton, images, fichiers) + (
            " Utilise UNIQUEMENT les informations de la source : n'invente ni chiffre, ni nom, ni date. "
            "Reformule et organise, sans rien ajouter.")
        utilisateur = f"Demande : {consigne or 'mets ce texte en forme'}\n\n{source}"
        schema = schema_generation(sorte, images, fichiers)
        res = self._appel(systeme, utilisateur, schema, max_jetons)
        if faits is not None:  # temps et jetons des deux étapes
            res.secondes += faits.secondes
            res.jetons_entree += faits.jetons_entree
            res.jetons_sortie += faits.jetons_sortie
            res.etapes = [{"faits": faits.donnees, "secondes": round(faits.secondes, 1)}]
        if res.donnees is not None:
            res.donnees["type"] = sorte
            res.donnees, res.corrections = nettoyer(res.donnees)
        return res

    # -- Mode 2 : sujet seul, en deux étapes ---------------------------------------------
    def plan(self, sujet: str, sorte: str, nb_parties: int = 5, ton: str = "formel") -> Resultat:
        unite = {"document": "sections", "presentation": "diapositives", "classeur": "feuilles"}[sorte]
        systeme = ("Tu rédiges en français et tu réponds uniquement en JSON. Propose le plan d'un "
                   f"{ {'document': 'document', 'presentation': 'diaporama', 'classeur': 'classeur'}[sorte]} : "
                   f"un titre et {nb_parties} {unite}, chacune avec un titre court et une idée (une phrase). "
                   + TONS.get(ton, TONS["formel"]))
        return self._appel(systeme, f"Sujet : {sujet}", _sans_maxlength(PLAN), 800)

    def rediger(self, plan: dict, sorte: str, ton: str = "formel", images: bool = True,
                fichiers: list[str] | None = None, max_jetons: int = 1200) -> Resultat:
        """Rédige partie par partie : chaque appel est court, ce qui convient aux petits modèles."""
        systeme = self._systeme(sorte, ton, images, fichiers) + (
            " Tu rédiges UNE seule partie d'un ensemble plus grand ; n'invente pas de statistiques précises.")
        schema = schema_generation(sorte, images, fichiers, partie=True)
        sommaire = "\n".join(f"{i}. {p['titre']}" for i, p in enumerate(plan["parties"], 1))
        parties, etapes, t, je, js = [], [], 0.0, 0, 0
        for i, p in enumerate(plan["parties"], 1):
            u = (f"Titre général : {plan['titre']}\nPlan :\n{sommaire}\n\n"
                 f"Rédige la partie {i} : « {p['titre']} ». Idée : {p['idee']}")
            r = self._appel(systeme, u, schema, max_jetons)
            t, je, js = t + r.secondes, je + r.jetons_entree, js + r.jetons_sortie
            etapes.append({"partie": p["titre"], "secondes": round(r.secondes, 1), "erreur": r.erreur})
            if r.donnees is None:
                continue
            if sorte == "document":
                r.donnees["titre"] = r.donnees.get("titre") or p["titre"]
            parties.append(r.donnees)
        cle = {"document": "sections", "presentation": "diapositives", "classeur": "feuilles"}[sorte]
        donnees = {"type": sorte, "titre": plan["titre"], cle: parties} if parties else None
        if sorte == "presentation" and parties:
            donnees[cle] = [{"mise_en_page": "titre", "titre": plan["titre"]}] + parties
        erreur = "; ".join(e["erreur"] for e in etapes if e["erreur"])
        corrections = []
        if donnees:
            donnees, corrections = nettoyer(donnees)
        return Resultat(donnees, "", t, je, js, erreur, etapes, corrections)
