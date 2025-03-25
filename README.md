> [!NOTE]
> Ce projet tente de traiter, nettoyer, structurer et analyser statistiquement une base de données issue d'un questionnaire rempli par des étudiants en troisième année de pré-master de l'[ENCGD](https://encgd.uiz.ac.ma/).

Un rapport final de ce projet est consultable via [ce lien.](https://walid-projects.notion.site/Projet-ADD-1a529a68f59c805a9e5fcb06292dff3e)

# Table des matières

- [Table des matières](#table-des-matières)
  - [Spécificités](#spécificités)
    - [Méthodes utilisées](#méthodes-utilisées)
  - [Usage](#usage)
    - [Installation](#installation)
      - [Debian/Ubuntu](#debianubuntu)
      - [Fedora](#fedora)
      - [Arch Linux](#arch-linux)
    - [Post installation](#post-installation)
      - [Windows](#windows)
      - [Linux/MacOS](#linuxmacos)
    - [Exécution](#exécution)
  - [Roadmap](#roadmap)

## Spécificités

### Méthodes utilisées

- Régression linéaire : Utilisé pour prédire et substituer les valeurs inconnues 

## Usage

Toutes contributions sont la bienvenues, vous devez en premier lieu :

### Installation

Installer Python 3.13.x sur votre machine, si vous êtes sur Windows ou MacOS, redirigez-vous sur [le site officiel](https://www.python.org/downloads), téléchargez le directement et exécuter le fichier `.exe` si Windows, sinon `.pkg` pour MacOS. Si vous êtes sous Linux, vous pouvez suivre la même étape mais il est préférable d'utiliser le gestionnaire de packets (packet manager) selon votre distribution :

#### Debian/Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-pip
```

#### Fedora

```bash
sudo dnf install python3 python3-pip
```

#### Arch Linux

```bash
sudo pacman -S python python-pip
```

### Post installation

Ce projet utilise des librairies externes que vous devez télécharger en exécutant la ligne de commande suivante selon votre système d'exploitation :

#### Windows

```bash
pip install -r requirements.txt
```

#### Linux/MacOS

Vous devez d'abord créer un environement virtuel d'exécution pour Python sur la racine de ce dossier. Pour ce faire, il faudra exécuter les lignes de commandes suivantes :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Exécution

Par défaut, ce programme génére trois documentations, [`DOCS.md`](./markdown/DOCS.md) avec une vue d'ensemble des variables de la base de donnée ainsi que des informations complémentaires. Il génére pour chaque variable des tableaux représentatifs des valeurs lors du traitement des données sur [`DATA.md`](./markdown/DATA.md). Il génére aussi pour chaque variable des statistiques descriptives sur [`STATS`](./markdown/STATS.md)

Ce programme génére aussi des images pour visualiser les données traitées et référencées sur les documentations.

Voici la ligne de commande génératrice de tout ceci :

```bash
py.exe .\analysis.py # Windows
python3 ./analysis.py # Linux/MacOS
```

_Vous pouvez optionnellement spécifier l'argument `--write="xyz"` pour choisir sur quel type de fichier écrire la documentation générée à l'exécution du programme._

## Roadmap

- [x] Codification de chaque variable + Documenter le processus
- [x] (Diapo 6 et 12) Afficher comme statistique les formats erronés/dupliqués/incohérentes/extrêmes
- [x] (Diapo 13) Générer un tabeleau "Vue des variables" comme partie de la documentation
- [x] (Diapo 17) Identifier les données manquantes + Documenter en créant un tableau statistiques avec toutes les variables et un tableau avec tout ces détails pour chaque variable
- [x] (Diapo 18) Par défaut, ignorer les valeurs manquantes. Si ces dernières constituent un taux entre 30% et 40%, il faudra supprimer la variable concernée si seulement le pourcentage des données manquantes est faible (15%) et réparti aléatoirement. Sinon si aucune de ces conditions ne sont satisfaites
- [ ] (Diapo 22) Gestion des données manquantes
  - [x] Régression linéaire
  - [ ] [Qualité de la prédiction](https://fr.wikipedia.org/wiki/R%C3%A9gression_lin%C3%A9aire#Qualit%C3%A9_de_la_pr%C3%A9diction) si l'hypothèse de linéarité est respectée
  - [x] Moyenne
  - [x] Médiane
  - [x] Mode
- [ ] (Diapo 28) Transformation ou permutation des villes par division limitrophe du continent africain
- [ ] (Diapo 48) Statistiques descriptives pour les variables catégorielles
