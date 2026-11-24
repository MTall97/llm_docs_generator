# llm_docs_generator

Expérience : un **petit modèle de langage qui tourne sur CPU** (et, plus tard, sur téléphone) peut-il
produire des documents **Markdown, PDF, PowerPoint et Excel** à partir d'un texte ou d'un sujet ?

Réponse courte, mesurée plus bas : **oui pour la mise en forme d'un texte fourni, avec un modèle de
3 milliards de paramètres et de la patience ; non pour rédiger un contenu fiable à partir d'un simple
sujet.** Le résultat n'est pas comparable à celui d'un grand modèle : voir « Ce qui ne marche pas ».

## Principe

```
texte ou sujet ──► petit modèle (GGUF, CPU) ──► JSON conforme au schéma ──► moteur de rendu ──► .md .pdf .pptx .xlsx
                    génération contrainte          (docgen/schema.py)      déterministe, sans IA
```

1. **Le modèle ne fabrique jamais de fichier.** Il remplit un schéma JSON sous *génération
   contrainte* : llama-cpp-python convertit le schéma en grammaire, et à chaque jeton seuls les jetons
   qui gardent le JSON conforme sont autorisés. Le JSON est donc toujours analysable et respecte la
   structure (types de blocs, mises en page autorisées, champs obligatoires).
2. **Un moteur de rendu sans IA** transforme le JSON en fichiers :
   Markdown, PDF (fpdf2), PowerPoint (python-pptx), Excel (openpyxl).
3. **Un seul schéma** pour trois sortes de livrables :
   - `document` : sections → blocs `paragraphe`, `liste`, `tableau`, `citation` et images ;
   - `presentation` : diapositives dont la mise en page est choisie dans une liste fermée :
     `titre`, `points`, `deux_colonnes`, `image_texte`, `chiffre_cle`, `citation` (+ notes de l'orateur) ;
   - `classeur` : feuilles → colonnes (avec format), lignes, **formules**, totaux, graphique.

Exemples complets : [`exemples/`](exemples/) (un JSON par sorte, couvrant tous les blocs).

### Formats produits

| | Markdown | PDF | PowerPoint | Excel |
|---|---|---|---|---|
| document | ✅ | ✅ | ✅ (une diapositive par section, conversion simple) | ✅ (ses tableaux seulement) |
| présentation | ✅ | ✅ (une page 16:9 par diapositive) | ✅ | – |
| classeur | ✅ (valeurs calculées) | ✅ (valeurs calculées) | – | ✅ (formules) |

### Excel : les calculs ne sont jamais confiés au modèle

Le modèle écrit les formules **avec des noms de colonnes** : `"formule": "{Prix} * {Quantité}"`.
Le moteur les traduit ligne par ligne en références A1 (`=B2*C2`) et ajoute les totaux
(`=SUM(D2:D5)`, fonctions `SOMME`, `MOYENNE`, `MIN`, `MAX`, `NB`). Le classeur reste juste si on
change une valeur. Les petits modèles se trompent souvent de lettre de colonne, beaucoup moins de nom.
Les nombres écrits en texte (« 1 200,50 € », « 12 % ») sont convertis. Les tests recalculent le classeur
avec LibreOffice pour vérifier les résultats des formules.

### Images

Par ordre de priorité, toutes rendues **sans IA** :

| Bloc | Ce que fait le modèle | Ce que fait l'outil |
|---|---|---|
| `image` | choisit **parmi les fichiers fournis** (`--images`) et écrit la légende ; la liste est fermée par la grammaire, il ne peut pas inventer de chemin | insère l'image |
| `graphique` | donne la forme (barres, courbes, camembert), les étiquettes et les valeurs | matplotlib (Markdown, PDF) ; **graphique natif** modifiable dans PowerPoint et Excel |
| `schema` | donne une liste de liens `{de, vers, etiquette}` (≤ 12) | écrit le code Graphviz et le rend avec `dot` |
| `icone` | donne un mot-clé (« budget », « écologie »…) | cherche dans 54 icônes [Tabler Icons](https://tabler.io/icons) embarquées (licence MIT, `docgen/icones/LICENSE-tabler-icons.txt`) |

Le bloc `schema` accepte aussi du code **Graphviz** ou **Mermaid** écrit à la main (ou par un plus grand
modèle) : Graphviz est rendu par `dot` ; Mermaid est gardé tel quel en Markdown (GitHub l'affiche) et
converti en Graphviz pour le PDF et le PowerPoint (organigrammes `graph`/`flowchart` seulement). Pas de
mermaid-cli : il faut Node et un Chromium, trop lourd pour l'objectif.
Pourquoi des liens plutôt que du code pour le modèle : lors des essais, le 3B écrivant du Graphviz libre a
bouclé (des arêtes ajoutées sans fin, 172 s, texte hors limite) ; une liste est bornée par la grammaire.

Si une image échoue (code invalide, icône inconnue, fichier absent), le document est produit quand même,
avec un avertissement à la place de l'image.

**Images générées par diffusion (SD-Turbo) : non intégrées.** Voir la mesure plus bas.

### Style

- **Visuel** : thèmes TOML dans [`themes/`](themes/) (palette, palette des graphiques, polices PDF et
  PowerPoint, taille du texte, marges, logo). `-t nature` ou `-t mon_theme.toml`.
- **Modèle PowerPoint de l'utilisateur** : `--modele-pptx charte.pptx` (ou `modele_pptx` dans le thème) ;
  les diapositives utilisent ses masques (« Titre », « Titre et contenu », « Deux contenus », « Titre seul »)
  et remplissent leurs espaces réservés.
- **Écriture** : `--ton formel | pedagogique | convivial | concis`, transmis au modèle.

## Installation

```bash
pip install -r requirements.txt
```

Graphviz pour les schémas (Debian/Ubuntu) :

```bash
sudo apt install graphviz
```

Télécharger un modèle (exemple : Qwen2.5 1,5B, 1,1 Go) :

```bash
mkdir -p modeles && curl -L -o modeles/qwen2.5-1.5b-instruct-q4_k_m.gguf https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

## Utilisation

Rendu seul, sans modèle :

```bash
python -m docgen rendre exemples/presentation.json -f pptx pdf md -o sortie/presentation
```

Mode « transformer un texte fourni » (le plus fiable) :

```bash
python -m docgen texte compte_rendu.txt -s presentation -m modeles/qwen2.5-3b-instruct-q4_k_m.gguf -o sortie/cr
```

Mode « sujet seul », en deux étapes : le modèle propose un plan, vous le modifiez, puis il rédige partie
par partie :

```bash
python -m docgen plan "Le compostage en appartement" -s document -o plan.json
```

```bash
python -m docgen rediger plan.json -s document -o sortie/compost
```

(`python -m docgen sujet "…"` enchaîne les deux sans pause.)

> ⚠️ **En mode « sujet seul », tout le contenu vient des connaissances du modèle**, qui sont limitées et
> souvent fausses pour un modèle de cette taille : faits inventés, chiffres plausibles mais faux,
> généralités. Ce mode produit un brouillon à vérifier ligne par ligne, pas un document fiable.

Le JSON produit est toujours enregistré (`sortie/cr.json`) : on peut le corriger à la main et relancer
`rendre`. Les corrections mécaniques appliquées (voir plus bas) sont affichées.

## Tests

```bash
python -m pytest -q
```

- `tests/test_rendu.py` (27 tests, sans modèle) : chaque JSON d'exemple → chaque format, fichiers
  relus (PDF, PPTX, XLSX), formules et totaux, graphiques natifs, modèle PowerPoint de l'utilisateur,
  conversion Mermaid, icônes, images en échec, validation, nettoyage. Le recalcul LibreOffice est
  ignoré si `soffice` est absent.
- `tests/test_generation.py` (4 tests) : ignorés si llama-cpp-python ou le modèle sont absents
  (`modeles/qwen2.5-0.5b-instruct-q4_k_m.gguf` ou variable `DOCGEN_MODELE_TEST`).

## Résultats mesurés

Banc d'essai : 15 demandes en français ([`banc/demandes.json`](banc/demandes.json)) :
- 11 « texte fourni », sur des textes fictifs pour pouvoir vérifier la fidélité : 4 documents, 4 présentations, 3 classeurs ;
- 4 « sujet seul ».

Conditions : Qwen2.5-Instruct 0.5B / 1.5B / 3B en GGUF Q4_K_M, CPU 4 cœurs, 15 Go de RAM, sans GPU, température 0,2. Détail complet, sorties JSON et fichiers produits : [`banc/RESULTATS.md`](banc/RESULTATS.md) et [`banc/resultats/`](banc/resultats/).

| | 0.5B | 1.5B | 3B |
|---|---|---|---|
| Fichier / mémoire max | 0,5 Go / 0,9 Go | 1,1 Go / 2,4 Go | 2,1 Go / 4,3 Go |
| Vitesse de génération | 18 jetons/s | 11,5 jetons/s | 7,4 jetons/s |
| Temps médian, texte → document / présentation / classeur | 15 / 21 / 17 s | 30 / 26 / 25 s | 65 / 49 / 36 s |
| Temps médian, sujet seul (plan + 4 parties) | 65 s | 95 s | 177 s |
| JSON conforme au schéma | 13/15 | 14/15 | 15/15 |
| Fichiers produits | 15/15 | 15/15 | 15/15 |
| **Relecture manuelle** (11 demandes « texte fourni ») : ✅ fidèle et complet | 0 | 0 | 2 |
| 🟡 juste mais incomplet ou ajout mineur | 0 | 2 | 4 |
| ❌ au moins une information fausse | **11** | **9** | **5** |

### Ce qui marche

- **La structure est garantie** : la génération contrainte donne un JSON analysable dans tous les cas,
  et des fichiers ont été produits pour 45 demandes sur 45 (avec le nettoyage mécanique). La mise en page,
  les thèmes, les graphiques natifs et les formules Excel ne dépendent pas du modèle : ils sont toujours
  corrects.
- **Le 3B reprend fidèlement les chiffres d'un texte fourni** : 85 % des chiffres de la source repris, et
  presque aucun chiffre absent de la source (les rares cas sont des graphiques inventés). Sur un compte
  rendu, une fiche pratique ou un rapport chiffré (T01 à T04), le résultat est utilisable après relecture.
- **Les formules par noms de colonnes** fonctionnent : quand le 3B fait un classeur, il écrit
  `{Prix unitaire} * {Quantité}` et `SOMME`, jamais un total calculé de tête.
- **Le rendu seul (sans modèle)** est fiable et rapide (moins d'une seconde) : 28 tests.

### Ce qui ne marche pas

- **Le 0.5B est inutilisable** : 11 sorties sur 11 contiennent une information fausse.
  - Avec un exemple dans la consigne, il le recopie (« Graisser la chaîne », « 4 bars pour un vélo de ville » dans un rapport de handball).
  - Sans exemple (`--sans-exemple` dans le banc), il ne recopie plus, mais il boucle, place des notes d'élèves dans des noms de colonnes et attribue mal les pourcentages : 8 sorties fausses sur 11.
- **Le 1.5B est à peine meilleur** (9 sur 11 fausses). Il réattribue des chiffres justes à de mauvais
  objets : « armoires chauffantes : 280 euros » alors que 280 € est le coût de la classe de mer. La mesure
  automatique ne voit pas ce genre d'erreur, puisque 280 figure bien dans la source.
- **Même le 3B se trompe** sur 5 demandes sur 11, surtout là où il faut comprendre et pas seulement
  recopier :
  - budget (C01) : 4 nuits × 31 € sans multiplier par les 64 personnes, donc un total faux, alors que la formule est bien construite ;
  - graphiques sans données à représenter (P01) : il invente les valeurs ;
  - interprétation (P02) : 97 % attribué à la glace au lieu des océans ;
  - choix de format (C03) : une moyenne sur 20 au format pourcentage, qui s'affiche « 1 400 % ».
- **Les images choisies par le modèle sont souvent décoratives ou fausses** : schémas sans signification
  (« Sorties → Cantine »), graphiques à une seule valeur non nulle, icônes absentes de la bibliothèque.
  Elles ne sont fiables que si les données s'y prêtent (évolution mensuelle de T03).
- **Le mode « sujet seul » est lent et invérifiable** : 1,5 à 3 minutes avec le 3B, contenu général et
  invérifiable. Il n'est pas évalué en relecture : il n'y a pas de source à laquelle comparer.
- **Boucles** : malgré la grammaire, un petit modèle peut répéter les mêmes diapositives jusqu'à la limite
  de jetons ; la grammaire borne le nombre d'éléments mais pas la répétition.
- **Limites techniques rencontrées** :
  - llama.cpp refuse les bornes de longueur (`maxLength`) du schéma : la grammaire dépasse sa profondeur maximale. Elles sont retirées pour la génération et vérifiées après coup, d'où quelques JSON « hors schéma » (texte trop long) qui sont tout de même rendus ;
  - le code Graphviz libre fait boucler le 3B : il a été remplacé, pour le modèle, par une liste de liens.

**Comparaison avec un grand modèle** : ces petits modèles ne sont pas comparables à un grand modèle
(Claude, GPT-4…), qui fait ce travail sans erreur de ce type dans la grande majorité des cas. Ce dépôt ne
mesure pas les grands modèles : le seul point de comparaison donné ici est la relecture ci-dessus.

### Corrections mécaniques (`docgen/nettoyage.py`)

Elles réparent la forme, jamais le contenu, et sont toutes signalées à l'utilisateur :
- lignes de tableau trop courtes ou trop longues ;
- séries de graphique de mauvaise longueur ;
- `"null"` écrit en texte et cellules entourées de `_…_` ;
- ligne d'en-têtes recopiée dans les données ;
- formule sans référence de colonne, ou mêlant nom et lettre (`C{Quantité}`, ajouté après le banc) ;
- totaux ou graphique sur une colonne inconnue ;
- numéros écrits dans les éléments d'une liste.

### Images générées par diffusion (SD-Turbo) : mesure

Mesure faite avec [`banc/mesurer_sd_turbo.py`](banc/mesurer_sd_turbo.py) (torch CPU, 4 threads, 1 ou 4 étapes) :

| Taille | 1 étape | 4 étapes |
|---|---|---|
| 512 × 512 | 8,5 s | 15 s |
| 256 × 256 | 2,3 s | 4,5 s |

Autres éléments :
- **ressources** : chargement en 13 s, mémoire maximale 6,4 Go, environ 5 Go à télécharger (modèle et torch) ;
- **qualité** : en 512 × 512, des illustrations décoratives correctes ; en 256 × 256, une qualité médiocre ; le texte dans les images est toujours illisible ;
- **licence** : Stability AI Community License, avec un usage commercial soumis à conditions (voir https://stability.ai/license).

Exemples dans [`banc/resultats/sd_turbo/`](banc/resultats/sd_turbo/).

**Décision : non intégré.** Le temps reste raisonnable sur PC, mais :
- il faut 6 Go de mémoire en plus du modèle de langage (4 Go pour le 3B), ce qui exclut le téléphone ;
- les images n'apportent aucune information, contrairement aux graphiques et aux schémas.

L'intégration serait simple (un bloc `illustration` avec une invite), si l'on accepte ces limites.

### Recommandation

- **Pour un usage réel sur PC** :
  - le **3B en mode « texte fourni »**, avec relecture systématique, surtout des chiffres calculés et des graphiques ;
  - images limitées aux graphiques tirés de la source (`--sans-images` sinon) ;
  - de préférence, le modèle n'écrit que le texte, et les tableaux chiffrés sont saisis ou vérifiés par l'utilisateur dans le JSON.
- **Pistes non testées ici** :
  - Qwen3 ou d'autres modèles de 3 à 4B ;
  - une quantification Q5/Q8 du 3B ;
  - une consigne qui demande d'abord d'extraire les faits du texte, puis de les mettre en forme ;
  - un affinage (*fine-tuning*) du 1.5B sur des paires texte → JSON.

## Piste téléphone (non réalisée)

L'architecture a été choisie pour que seul le moteur change :

| Élément | PC (ce dépôt) | Téléphone (à faire) |
|---|---|---|
| Schéma JSON | `docgen/schema.py` | **le même** (exporté en JSON) |
| Modèle | llama-cpp-python, GGUF Q4 | [wllama](https://github.com/ngxson/wllama) (llama.cpp en WebAssembly, mêmes fichiers GGUF, grammaires prises en charge) ou [WebLLM](https://github.com/mlc-ai/web-llm) (WebGPU, sortie JSON contrainte) ; application native : [MLC LLM](https://llm.mlc.ai/) ou llama.cpp compilé pour Android/iOS |
| Rendu | fpdf2, python-pptx, openpyxl, matplotlib | [jsPDF](https://github.com/parallax/jsPDF), [PptxGenJS](https://gitbrent.github.io/PptxGenJS/) (graphiques natifs compris), [SheetJS](https://sheetjs.com/) (la version libre écrit les formules mais pas les graphiques), Chart.js pour les images de graphiques |
| Schémas | Graphviz `dot` | [viz.js](https://github.com/mdaines/viz-js) (Graphviz en WebAssembly) ou Mermaid, natif en JS |
| Icônes | SVG Tabler → PNG (cairosvg) | SVG directement |

Ordres de grandeur attendus, **non mesurés ici** : un téléphone récent fait tourner un modèle de
0,5 à 1,5 milliard de paramètres en Q4 ; le 3B demande environ 2,5 Go de mémoire libre, au-delà de
beaucoup d'appareils. Le WebAssembly sur CPU est plusieurs fois plus lent que llama.cpp natif : avec les
temps mesurés sur le PC (voir plus haut), il faut s'attendre à plusieurs minutes par document. À mesurer
avant tout développement.

## Organisation du dépôt

```
docgen/
  schema.py          schéma JSON commun, validation, schéma de génération
  generation.py      llama-cpp-python : texte → JSON, plan puis parties
  nettoyage.py       corrections mécaniques (forme seulement)
  theme.py           thèmes TOML
  rendu/             markdown.py, pdf.py, pptx.py, xlsx.py, images.py (sans IA)
  icones/            54 icônes Tabler (MIT) + index de mots-clés français
  __main__.py        ligne de commande
themes/              sobre.toml, nature.toml
exemples/            un JSON complet par sorte de livrable
tests/               test_rendu.py (sans modèle), test_generation.py (modèle requis)
banc/                demandes, lancer.py, rapport.py, relecture.csv, RESULTATS.md, resultats/
```

Pour relancer le banc :

```bash
python banc/lancer.py modeles/qwen2.5-3b-instruct-q4_k_m.gguf
```

```bash
python banc/rapport.py
```
