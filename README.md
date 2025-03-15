# Hellow

> [!WARNING]
> Ce code est très instable et inutilisable sans base de données pour être utiliser à des intérêts externes.

Le rapport final est présenté sur [ce lien.](https://walid-projects.notion.site/Projet-ADD-1a529a68f59c805a9e5fcb06292dff3e)

## Spécificités

- Temps passé sur le projet : +100h
- IDE utilisé : Visual Studio Code
- EOL Sequence : LF

## Installation

```bash
pip install snakemd scipy
```

### Roadmap

- [x] Codification de chaque variable + Documenter le processus
- [ ] (Diapo 6 et 12) Afficher comme statistique les formats erronés/dupliqués/incohérentes/extrêmes
- [ ] (Diapo 13) Générer un tabeleau "Vue des variables" comme partie de la documentation
- [x] (Diapo 17) Identifier les données manquantes + Documenter en créant un tableau statistiques avec toutes les variables et un tableau avec tout ces détails pour chaque variable
- [x] (Diapo 18) Par défaut, ignorer les valeurs manquantes. Si ces dernières constituent un taux entre 30% et 40%, il faudra supprimer la variable concernée si seulement le pourcentage des données manquantes est faible (15%) et réparti aléatoirement. Sinon si aucune de ces conditions ne sont satisfaites
- [x] (Diapo 22) Ajouter la moyenne, médianne et Mode et/ou possiblement l'imputation multiple
- [ ] (Diapo 24) Ajouter un tableau "Variables de résultat" après remplaçage des données manquantes
- [ ] (Diapo 26) Imputation avancée au niveau du traitement des données manquantes
  - [x] Régression linéaire
  - [ ] Imputation multiple
- [-] (Diapo 28) Transformation ou permutation des villes par division limitrophe du continent africain
- [ ] (Diapo 46) Détection des valeurs aberrantes (outliers)
