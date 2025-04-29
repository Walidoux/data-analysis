> [!NOTE]
> Ce projet tente de traiter, nettoyer, structurer et analyser statistiquement une base de données issue d'un questionnaire rempli par des étudiants en troisième année pré-master de l'[ENCGD](https://encgd.uiz.ac.ma/).

Un rapport final de ce projet est consultable via [ce lien](https://walid-projects.notion.site/Projet-ADD-1a529a68f59c805a9e5fcb06292dff3e). Vous trouverez tout les détails et explications à la réalisation de ce projet.

- [Spécificités](#spécificités)
  - [Méthodes utilisées](#méthodes-utilisées)
  - [Détails](#détails)
- [Usage](#usage)
  - [Installation](#installation)
  - [Post-installation](#post-installation)
  - [Exécution](#exécution)
  - [Arguments (paramètres)](#arguments-paramètres)

## Spécificités

### Méthodes utilisées

- Régression linéaire : Utilisé pour prédire et substituer les valeurs inconnues/invalides par des approximaions équivalentes
- Tests statistiques : Test de Khi-Deux, test t pour échantillon unique/indépendant, ANOVA à 1 facteur
- Représentations graphiques : Histogrammes, diagrammes, choroplèthe, boxplots, matrice de corrélation.

### Détails

- Début officiel du projet : 05 Mars 2025
- Temps moyennement investi : +200h

## Usage

Toutes contributions sont la bienvenues, vous devez en premier lieu :

### Installation

Installer Python 3.13.x sur votre machine, si vous êtes sur Windows ou MacOS, redirigez-vous sur [le site officiel](https://www.python.org/downloads), téléchargez le directement et exécuter le fichier `.exe` si Windows, sinon `.pkg` pour MacOS. Si vous êtes sous Linux, vous pouvez suivre la même étape mais il est préférable d'utiliser le gestionnaire de packets (packet manager) selon votre distribution :

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install python3 python3-pip

# Fedora
sudo dnf install python3 python3-pip

# Arch Linux
sudo pacman -S python python-pip
```

### Post-installation

Ce projet utilise des librairies externes que vous devez télécharger en exécutant la ligne de commande suivante selon votre système d'exploitation :


```bash
# Windows
pip install -r requirements.txt

# Linux
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

### Arguments (paramètres)

- `--write="NONE"` : Ajouter cet argument permet de spécifier sur quel type de fichier écrire la documentation générée à l'exécution du programme qui peut prend les valeurs correpondant aux noms des fichiers sur le dossier [markdown ici](./markdown). `NONE` veut dire aucune écriture. Vous pouvez spécifier plusieurs types de fichiers en séparant par une virgule.

- `--skip-geolocation` : Ignorer l'étape de génénaration de la carte choroplèthe. Le service externe de géolocalisation des villes prend beaucoup de temps à s'exécuter.

- `--skip-visualization` : Ignorer l'étape de génération des représentations graphiques.
