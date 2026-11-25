# Résultats du banc d'essai

Généré par `python banc/rapport.py` à partir de `banc/resultats/*/mesures.csv`.
Machine : CPU 4 cœurs, 15 Go de RAM, sans GPU ; modèles GGUF Q4_K_M ; llama-cpp-python, 4 threads, température 0,2.

## Synthèse par modèle

| | qwen2.5-0.5b | qwen2.5-0.5b-sans-exemple | qwen2.5-1.5b | qwen2.5-3b | qwen2.5-3b-deux-temps | qwen3-4b-2507 | qwen3-4b-2507-deux-temps |
|---|---|---|---|---|---|---|---|
| Taille du fichier | 491 Mo | 491 Mo | 1117 Mo | 2105 Mo | 2105 Mo | 2497 Mo | 2497 Mo |
| Mémoire max du processus | 949 Mo | 917 Mo | 2384 Mo | 4258 Mo | 4263 Mo | 6321 Mo | 6303 Mo |
| Chargement du modèle | 0.3 s | 0.3 s | 0.6 s | 0.7 s | 1.2 s | 3.7 s | 1.8 s |
| Consigne | un temps | un temps, sans exemple | un temps | un temps | deux temps | un temps | deux temps |
| JSON valide (structure du schéma) | 13/15 | 13/15 | 14/15 | 15/15 | 10/11 | 14/15 | 11/11 |
| Fichiers produits | 15/15 | 14/15 | 15/15 | 15/15 | 11/11 | 15/15 | 11/11 |
| Échecs « limite de jetons » (boucle) | 1 | 2 | 1 | 0 | 0 | 0 | 0 |
| Corrections mécaniques (moyenne) | 1.9 | 6.1 | 2.0 | 0.5 | 0.7 | 0.5 | 0.4 |
| Recopie de l'exemple de la consigne (demandes touchées) | 4 | 0 | 2 | 1 | 0 | 0 | 0 |
| Vitesse (jetons produits / s, médiane) | 18.1 | 17.9 | 11.5 | 7.4 | 6.0 | 5.1 | 4.9 |
| Temps médian, document depuis un texte | 15 s | 64 s | 30 s | 65 s | 164 s | 190 s | 299 s |
| Temps médian, presentation depuis un texte | 21 s | 16 s | 26 s | 49 s | 127 s | 92 s | 184 s |
| Temps médian, classeur depuis un texte | 17 s | 30 s | 25 s | 36 s | 105 s | 75 s | 172 s |
| Temps médian, sujet seul (plan + parties) | 65 s | 93 s | 95 s | 177 s | – | 486 s | – |
| Fidélité auto. : chiffres absents de la source (moyenne) | 12 % | 5 % | 9 % | 8 % | 15 % | 24 % | 5 % |
| Couverture : chiffres de la source repris (moyenne) | 54 % | 76 % | 69 % | 85 % | 71 % | 76 % | 89 % |
| Mots pleins absents de la source (moyenne) | 29 % | 26 % | 17 % | 24 % | 24 % | 42 % | 38 % |
| Relecture manuelle, ✅ fidèle et complet | 0/11 | 0/11 | 0/11 | 2/11 | 1/11 | 1/11 | 2/11 |
| Relecture manuelle, 🟡 incomplet ou ajout mineur | 0/11 | 3/11 | 2/11 | 4/11 | 2/11 | 4/11 | 4/11 |
| Relecture manuelle, ❌ information fausse | 11/11 | 8/11 | 9/11 | 5/11 | 8/11 | 6/11 | 5/11 |

Lecture : les lignes « Fidélité », « Couverture » et « Mots pleins » portent sur les demandes « texte fourni » dont le JSON est valide ; la relecture manuelle sur les 11 demandes « texte fourni ». « Recopie de l'exemple » compte les demandes dont la sortie reprend mot pour mot un texte de plus de 9 caractères de l'exemple de la consigne (un sujet de vélo). « Chiffres absents de la source » compte les nombres (hors entiers de 0 à 10) qui ne figurent pas dans le texte source, ni ×100 ni ÷100 : ce sont des chiffres inventés, mal recopiés ou calculés par le modèle. « Mots pleins absents » est un indicateur grossier d'ajouts (mots de six lettres ou plus, comparés sur leurs six premières lettres) : une reformulation légitime l'augmente aussi.

## Détail par demande

| Demande | Sorte | Mode | qwen2.5-0.5b | qwen2.5-0.5b-sans-exemple | qwen2.5-1.5b | qwen2.5-3b | qwen2.5-3b-deux-temps | qwen3-4b-2507 | qwen3-4b-2507-deux-temps |
|---|---|---|---|---|---|---|---|---|---|
| T01 | document | texte | valide 14 s, inventés 0 % | échec 189 s, boucle | valide 53 s, inventés 0 % | valide 66 s, inventés 0 % | valide 175 s, inventés 0 % | valide 117 s, inventés 0 % | valide 385 s, inventés 4 % |
| T02 | document | texte | valide 36 s, inventés 0 % | valide 7 s, inventés 0 % | valide 20 s, inventés 0 % | valide 64 s, inventés 0 % | valide 86 s, inventés 0 % | valide 173 s, inventés 100 % | valide 240 s, inventés 0 % |
| T03 | document | texte | valide 16 s, inventés 30 % | hors schéma 16 s, inventés 0 % | valide 36 s, inventés 5 % | valide 88 s, inventés 0 % | valide 194 s, inventés 8 % | valide 207 s, inventés 0 % | valide 331 s, inventés 5 % |
| T04 | document | texte | valide 14 s, inventés 0 % | valide 112 s, inventés 0 % | valide 24 s, inventés 0 % | valide 58 s, inventés 0 % | valide 153 s, inventés 0 % | valide 261 s, inventés 0 % | valide 266 s, inventés 20 % |
| P01 | presentation | texte | hors schéma 18 s, inventés 0 % | valide 68 s, inventés 14 % | valide 18 s, inventés 0 % | valide 51 s, inventés 21 % | valide 137 s, inventés 60 % | valide 94 s, inventés 35 % | valide 149 s, inventés 22 % |
| P02 | presentation | texte | valide 46 s, inventés 50 % | valide 12 s, inventés 0 % | hors schéma 173 s, inventés 0 % | valide 47 s, inventés 67 % | hors schéma 127 s, inventés 100 % | valide 90 s, inventés 100 % | valide 186 s, inventés 0 % |
| P03 | presentation | texte | valide 24 s, inventés 0 % | valide 13 s, inventés 0 % | valide 19 s, inventés 0 % | valide 64 s, inventés 0 % | valide 127 s, inventés 0 % | valide 97 s, inventés 22 % | valide 232 s, inventés 0 % |
| P04 | presentation | texte | valide 10 s, inventés 0 % | valide 18 s, inventés 0 % | valide 32 s, inventés 0 % | valide 37 s, inventés 0 % | valide 110 s, inventés 0 % | valide 68 s, inventés 0 % | valide 182 s, inventés 0 % |
| C01 | classeur | texte | valide 17 s, inventés 9 % | valide 96 s, inventés 35 % | valide 22 s, inventés 40 % | valide 57 s, inventés 0 % | valide 105 s, inventés 80 % | valide 75 s, inventés 9 % | valide 204 s, inventés 0 % |
| C02 | classeur | texte | valide 22 s, inventés 0 % | valide 30 s, inventés 0 % | valide 25 s, inventés 41 % | valide 36 s, inventés 0 % | valide 107 s, inventés 0 % | valide 50 s, inventés 0 % | valide 172 s, inventés 0 % |
| C03 | classeur | texte | valide 17 s, inventés 35 % | valide 27 s, inventés 0 % | valide 48 s, inventés 0 % | valide 35 s, inventés 0 % | valide 92 s, inventés 0 % | valide 77 s, inventés 0 % | valide 152 s, inventés 0 % |
| S01 | document | sujet | valide 63 s | valide 102 s | valide 104 s | valide 185 s | – | valide 710 s | – |
| S02 | document | sujet | valide 107 s, boucle | valide 180 s, boucle | valide 143 s, boucle | valide 170 s | – | valide 618 s | – |
| S03 | presentation | sujet | hors schéma 49 s | valide 37 s | valide 39 s | valide 62 s | – | valide 110 s | – |
| S04 | classeur | sujet | valide 68 s | valide 84 s | valide 85 s | valide 191 s | – | hors schéma 354 s | – |

« valide » : JSON conforme et fichiers produits (ce qui ne dit rien de la justesse du contenu) ; « hors schéma » : fichiers produits mais un texte trop long ou trop d'éléments ; « échec » : aucun fichier. « inventés » : part des nombres absents de la source (mesure automatique).


## Relecture manuelle (demandes « texte fourni »)

Les mesures automatiques ne voient pas un chiffre de la source mal attribué ni un calcul faux fait avec des chiffres justes. Chaque sortie a donc été relue. Règle : ❌ si un lecteur repart avec une information fausse (chiffre, calcul, graphique trompeur, contenu de l'exemple) ; 🟡 si c'est juste mais incomplet ou avec un ajout sans conséquence ; ✅ sinon.

| Modèle | Demande | Note | Justification |
|---|---|---|---|
| qwen2.5-3b | T01 | 🟡 | Fidèle et complet ; deux schémas sans signification (Sorties → Cantine). |
| qwen2.5-3b | T02 | 🟡 | Étapes fidèles ; une citation inventée (« Le rempotage est une occasion idéale… »). |
| qwen2.5-3b | T03 | ✅ | Tableau et courbe exacts ; tout le texte repris. |
| qwen2.5-3b | T04 | 🟡 | Procédure fidèle ; schéma simplifié avec un nœud « Banque » ajouté ; citation redondante ; délai de 30 jours omis dans les étapes. |
| qwen2.5-3b | P01 | ❌ | Graphique inventé (« stages par année » 2025 : 1 ; 2026 : 4) ; recettes absentes. |
| qwen2.5-3b | P02 | ❌ | « 97 % » attribué à la glace (c'est la part des océans) ; graphique aux valeurs inventées ; sous-titre recopié de l'exemple. |
| qwen2.5-3b | P03 | ❌ | Bonne comparaison des coûts mais « mises à jour : Offre B téléphoniques » est faux (c'est l'assistance). |
| qwen2.5-3b | P04 | 🟡 | Chiffres exacts ; icône « étoile » absente de la bibliothèque (avertissement à la place). |
| qwen2.5-3b | C01 | ❌ | Chiffres repris mais calcul faux : hébergement 4 × 31 € sans les 64 personnes ; repas et assurance idem ; total général faux. |
| qwen2.5-3b | C02 | ✅ | Quantités et prix exacts ; formule « C{Quantité} * C{Prix unitaire} » cassée dans Excel avant la correction mécanique ajoutée après ce banc. |
| qwen2.5-3b | C03 | ❌ | Notes exactes et formule de moyenne juste mais colonne au format pourcentage (14 s'affiche 1 400 %). |
| qwen2.5-1.5b | T01 | ❌ | Armoires chauffantes « 280 euros » et « costume par élève 280 euros » : chiffres réattribués. |
| qwen2.5-1.5b | T02 | ❌ | Lignes de l'exemple (« Nettoyer la chaîne ») mélangées aux étapes ; fiche incomplète. |
| qwen2.5-1.5b | T03 | ❌ | Graphique trompeur (semestre 2026 : 250 ; 2025 : 0) ; répartition des ventes absente. |
| qwen2.5-1.5b | T04 | ❌ | Étapes correctes puis section recopiée de l'exemple (« Nettoyer la chaîne »). |
| qwen2.5-1.5b | P01 | 🟡 | Trois diapositives exactes mais finances et projet 2027 absents. |
| qwen2.5-1.5b | P02 | ❌ | Boucle (mêmes diapositives répétées) ; titre et chiffre inversés. |
| qwen2.5-1.5b | P03 | 🟡 | Deux diapositives exactes ; ni coûts sur trois ans ni décision. |
| qwen2.5-1.5b | P04 | ❌ | Graphique « sujets de mécontentement » qui y range l'accueil (noté 8 |
| qwen2.5-1.5b | C01 | ❌ | Car multiplié par 58 élèves ; noms de feuille et de colonne de l'exemple (« Achats » |
| qwen2.5-1.5b | C02 | ❌ | Prix faux (pâtes 6 |
| qwen2.5-1.5b | C03 | ❌ | Une feuille par élève avec des notes mélangées et inventées ; pas de formule. |
| qwen2.5-0.5b | T01 | ❌ | Tableau et liste recopiés de l'exemple (vélo). |
| qwen2.5-0.5b | T02 | ❌ | Tableau de l'exemple (« Pompe : gonfler les pneus »). |
| qwen2.5-0.5b | T03 | ❌ | Chiffres en milliers tronqués (38 au lieu de 38 200) ; six camemberts absurdes ; liste de l'exemple. |
| qwen2.5-0.5b | T04 | ❌ | Étapes inventées (« Nettoyer les documents ») mêlées à l'exemple. |
| qwen2.5-0.5b | P01 | ❌ | Diapositives de l'exemple (« Graisser la chaîne » |
| qwen2.5-0.5b | P02 | ❌ | Boucle de diapositives « 4 bars pour un vélo de ville ». |
| qwen2.5-0.5b | P03 | ❌ | Points exacts mais camembert comparant 49 € par mois et 3 600 € par an. |
| qwen2.5-0.5b | P04 | ❌ | Répétitions ; « Pression sur les jeux vidéo ». |
| qwen2.5-0.5b | C01 | ❌ | Colonnes incohérentes ; feuille « Achats » de l'exemple. |
| qwen2.5-0.5b | C02 | ❌ | Une feuille par produit ; prix absents. |
| qwen2.5-0.5b | C03 | ❌ | Feuille « Achats » de l'exemple ; aucune note d'élève. |
| qwen2.5-0.5b-sans-exemple | T01 | ❌ | Boucle jusqu'à la limite de jetons : aucun fichier. |
| qwen2.5-0.5b-sans-exemple | T02 | 🟡 | Un seul paragraphe exact ; les étapes manquent. |
| qwen2.5-0.5b-sans-exemple | T03 | 🟡 | Paragraphe exact ; liste des mois sans valeur ; sous-titre absurde (« graphique de la farine »). |
| qwen2.5-0.5b-sans-exemple | T04 | 🟡 | Paragraphes fidèles entrecoupés de listes de mots-clés sans intérêt. |
| qwen2.5-0.5b-sans-exemple | P01 | ❌ | Colonnes gauche et droite identiques ; chiffres absents de la source. |
| qwen2.5-0.5b-sans-exemple | P02 | ❌ | Une seule diapositive ; « les lacs et les rivières s'infiltrent dans le sol ». |
| qwen2.5-0.5b-sans-exemple | P03 | ❌ | Offre A présentée deux fois (la seconde avec le coût de 11 784 €) ; offre B absente. |
| qwen2.5-0.5b-sans-exemple | P04 | ❌ | « 47 % dans 15-25 ans » (47 % demandent des places assises). |
| qwen2.5-0.5b-sans-exemple | C01 | ❌ | « 9800 euros » répété dans toutes les colonnes. |
| qwen2.5-0.5b-sans-exemple | C02 | ❌ | Une feuille par produit ; quantités remplacées par un numéro d'ordre ; pas de prix. |
| qwen2.5-0.5b-sans-exemple | C03 | ❌ | Notes placées dans les noms de colonnes ; aucune valeur. |
| qwen3-4b-2507 | T01 | 🟡 | Exact mais incomplet : cantine |
| qwen3-4b-2507 | T02 | ❌ | Conseils inventés présentés comme faits (« moins de 2 cm : risque de surcharge » |
| qwen3-4b-2507 | T03 | ❌ | Tableaux et graphiques exacts |
| qwen3-4b-2507 | T04 | ❌ | Procédure très complète |
| qwen3-4b-2507 | P01 | 🟡 | Chiffres exacts |
| qwen3-4b-2507 | P02 | ❌ | Graphique « parcours de l'eau » aux valeurs inventées (1 |
| qwen3-4b-2507 | P03 | 🟡 | Comparaison juste avec calculs corrects (294 €/mois |
| qwen3-4b-2507 | P04 | 🟡 | Chiffres exacts ; citation inventée (« Le dimanche |
| qwen3-4b-2507 | C01 | ❌ | 64 personnes et prix du car par personne justes |
| qwen3-4b-2507 | C02 | ✅ | Quantités |
| qwen3-4b-2507 | C03 | ❌ | Formule « {Contrôle 1} + {Contrôle 2} + {Devoir maison} / 3 » sans parenthèses : moyennes fausses. |
| qwen3-4b-2507-deux-temps | T01 | 🟡 | Complet et exact (toutes les rubriques) ; graphiques à une seule valeur ; « bonne réactivité du personnel » ajouté. |
| qwen3-4b-2507-deux-temps | T02 | 🟡 | Étapes exactes ; graphiques inutiles (2 et 4 cm |
| qwen3-4b-2507-deux-temps | T03 | ❌ | Tout est exact et le pic est bien en mai |
| qwen3-4b-2507-deux-temps | T04 | ❌ | Procédure exacte |
| qwen3-4b-2507-deux-temps | P01 | 🟡 | Exact |
| qwen3-4b-2507-deux-temps | P02 | ❌ | Diapositives exactes (97 % |
| qwen3-4b-2507-deux-temps | P03 | ✅ | Comparaison complète et exacte |
| qwen3-4b-2507-deux-temps | P04 | 🟡 | Chiffres exacts ; graphique à une barre ; un chiffre présenté comme une citation. |
| qwen3-4b-2507-deux-temps | C01 | ❌ | Formule à trois facteurs (personnes × prix × durée) mais durées écrites en texte (« 4 nuits ») : erreur dans Excel ; car multiplié par 64. |
| qwen3-4b-2507-deux-temps | C02 | ✅ | Quantités |
| qwen3-4b-2507-deux-temps | C03 | ❌ | Même formule sans parenthèses qu'en un temps : moyennes fausses. |
| qwen2.5-3b-deux-temps | T01 | 🟡 | Exact mais cantine absente ; schémas sans signification (« Prochain conseil → Sorties »). |
| qwen2.5-3b-deux-temps | T02 | ❌ | Un seul paragraphe |
| qwen2.5-3b-deux-temps | T03 | ❌ | Tableau exact mais graphique « coût de la farine » inventé (2025 : 100 ; 2026 : 111). |
| qwen2.5-3b-deux-temps | T04 | 🟡 | Étapes exactes (délai de 30 jours omis) ; schéma absurde (boucles d'un nœud sur lui-même). |
| qwen2.5-3b-deux-temps | P01 | ❌ | Graphique « évolution des sections » qui montre en fait les recettes en milliers. |
| qwen2.5-3b-deux-temps | P02 | ❌ | Une seule diapositive ; sous-titre qui boucle (« Atelier du samedi 15 juillet 2023 - Atelier de collège… »). |
| qwen2.5-3b-deux-temps | P03 | ❌ | Graphique « coût par an » avec 49 et 49 (prix mensuel) ; total de l'offre B absent. |
| qwen2.5-3b-deux-temps | P04 | ❌ | Chiffres exacts mais graphique « avant / après » inventé. |
| qwen2.5-3b-deux-temps | C01 | ❌ | Montants calculés de tête et faux (hébergement 43 164 € au lieu de 7 936 €) ; aucune formule. |
| qwen2.5-3b-deux-temps | C02 | ✅ | Quantités |
| qwen2.5-3b-deux-temps | C03 | ❌ | Formule de moyenne juste (avec parenthèses) mais colonne au format pourcentage (1 400 %). |