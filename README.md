# Concepteur de Grille LCN

Outil web local pour concevoir la grille hebdomadaire d'une radio, avec une base pensée pour devenir réutilisable et open source.

## Répertoire privé local

Les fichiers personnels et générés par ton instance locale sont désormais rangés dans `prive/`.

- `prive/config.local.json`
- `prive/grille-programmes.json`
- `prive/grille-programmes.jsonl`
- `prive/genres_bibliotheque_complete.csv`
- `prive/run/grille-designer-runtime.json`

Ce dossier est destiné à rester local et ne doit pas partir sur GitHub.

## Publication et données locales

Ce répertoire est la version publiable du projet.

- le code peut partir sur GitHub
- le dossier `prive/` doit rester local sur la machine qui exécute l’outil

Le dépôt public peut contenir un fichier [config.example.json](config.example.json) neutre, sans chemins réels ni secrets.

## Ce que fait l’outil

- affiche les 7 jours de la semaine, de `00:00` à `24:00`
- charge une grille actuelle, ou une grille vierge
- édite les créneaux à la souris sur une base de `5 minutes`
- distingue les blocs continus et les émissions ponctuelles superposables
- permet de choisir une source par créneau : playlist `.m3u` ou mode `random`
- permet de modifier les horaires, le type de créneau, le chemin source et les notes
- intègre la bibliothèque de tags issue de la supervision et de la cartographie documentaire
- mémorise automatiquement un brouillon dans le navigateur
- sauvegarde la grille sur disque en `JSON`
- exporte aussi un `JSONL` à plat, utile pour `radio.liq` et `generate_pools.py`
- ajoute des réglages d’habillage pour les jingles et les réclames

## Lancer l’outil

Depuis Finder :

1. double-clique `lancer-concepteur-grille.command`

Ou depuis le terminal :

```bash
cd LCN-Tools/Concepteur-Grille
python3 grille_designer_app.py
```

L’application ouvre ensuite une page locale dans le navigateur.

## Fichiers générés

- `prive/grille-programmes.json`
- `prive/grille-programmes.jsonl`
- `prive/config.local.json`

## Tests utiles

```bash
cd LCN-Tools/Concepteur-Grille
python3 -m py_compile grille_designer_app.py
python3 -m unittest tests/test_grille_designer_app.py
node --check web/assets/js/app.js
```
