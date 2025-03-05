from unicodedata import normalize as unicodedata_normalize
from collections import Counter
from csv import reader
from enum import Enum, auto

import re
import snakemd


adjusted_data = open("output.csv", "w")
doc = snakemd.Document()


class Listable(Enum):
    @classmethod
    def get(cls) -> list[str]:
        return [c.name for c in cls]


def normalize(value: str) -> str:
    return (
        unicodedata_normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    )


def numeric_data(value: str):
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


class StoreCollection:
    def __init__(self, pos):
        self.pos = pos
        self.data = {}

    def is_unknown(self, value: str) -> bool:
        return value == "N.V" or not value.replace(" ", "").isalnum() or not value

    # extracts distinct values
    def known_posibilities(self, value: str, write=True):
        value = normalize(value).upper()

        possible_values = self.in_depth(value)
        if len(possible_values) > 1:
            for possible_value in possible_values:
                self.known_posibilities(possible_value, write)

        # TODO : Handle unknown value
        if self.is_unknown(value):
            return

        if not self.data:
            adjusted_data.write(f"{value}\n") if write else None
            self.data[len(self.data)] = value
            return
        for _, info in self.data.items():
            if info == value:
                return
        adjusted_data.write(f"{value}\n") if write else None
        self.data[len(self.data)] = value

    def in_depth(self, value: str):
        match = re.search(r"[;,/]| ET ", value)
        matches = []

        if match:
            for v in value.split(match.group()):
                if not self.is_unknown(v):
                    matches.append(v)
            return [value]
        return [value]

    def subscribe(self, value: str, approx=False, exact=False, format=True):
        value = normalize(value).upper() if format else value
        possible_values = self.in_depth(value)

        if len(possible_values) > 1:
            for possible_value in possible_values:
                self.subscribe(possible_value, approx, exact, format)

        # TODO : Handle unknown value
        if self.is_unknown(value):
            return

        for key, info in self.data.items():
            if approx and does_match(value, info["name"]):
                self.data[key]["count"] += 1
                return
            elif not approx and exact and info["name"] == value:
                self.data[key]["count"] += 1
                return
            elif not exact and info["name"] in value:
                self.data[key]["count"] += 1
                return
        self.data[len(self.data)] = {"name": value, "count": 1}


class IntSet:
    def __init__(self, data: list[int]):
        self.data = data

    def store(self, value: int):
        self.data.append(value)


# Référence: https://fr.wikipedia.org/wiki/Distance_de_Levenshtein
def levenshtein_distance(v1: str, v2: str):
    # Create a matrix to store distances
    rows = len(v1) + 1
    cols = len(v2) + 1
    dist = [[0 for _ in range(cols)] for _ in range(rows)]

    # Initialize the matrix
    for i in range(1, rows):
        dist[i][0] = i
    for j in range(1, cols):
        dist[0][j] = j

    # Fill the matrix
    for i in range(1, rows):
        for j in range(1, cols):
            if v1[i - 1] == v2[j - 1]:
                cost = 0
            else:
                cost = 1
            dist[i][j] = min(
                dist[i - 1][j] + 1,  # Deletion
                dist[i][j - 1] + 1,  # Insertion
                dist[i - 1][j - 1] + cost,  # Substitution
            )

    # Return the final distance
    return dist[-1][-1]


def does_match(s1: str, s2: str, threshold=2):
    distance = levenshtein_distance(s1, s2)
    return distance <= threshold


# Référence: https://fr.wikipedia.org/wiki/Corr%C3%A9lation_(statistiques)
def correlation(data: list) -> int:
    X = [i for i, x in enumerate(data) if x is not None]  # Indices des valeurs connues
    y = [x for x in data if x is not None]  # Valeurs connues

    n = len(X)
    sum_x = sum(X)
    sum_y = sum(y)
    sum_xy = sum(x * y for x, y in zip(X, y))
    sum_x2 = sum(x**2 for x in X)
    sum_y2 = sum(y**2 for y in y)

    numerator = sum_xy - (sum_x * sum_y) / n
    denominator_x = (sum_x2 - (sum_x**2) / n) ** 0.5
    denominator_y = (sum_y2 - (sum_y**2) / n) ** 0.5
    denominator = denominator_x * denominator_y

    # éviter le cas infini en divisant par zéro
    return abs(numerator / denominator) if denominator != 0 else 0


def predict_missing_value(data: list[int]) -> list[int]:
    missing_indices = [i for i, x in enumerate(data) if x is None]

    X = [i for i, x in enumerate(data) if x is not None]  # Indices des valeurs connues
    y = [x for x in data if x is not None]  # Valeurs connues

    n = len(X)
    sum_x = sum(X)
    sum_y = sum(y)
    sum_xy = sum(x * y for x, y in zip(X, y))
    sum_x2 = sum(x**2 for x in X)

    a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
    b = (sum_y - a * sum_x) / n

    for i in missing_indices:
        data[i] = round(a * i + b)  # y = ax + b

    return data


class Option(Listable):
    EXP = auto()
    MATH = auto()
    ECO = auto()

    @classmethod
    def classify(self, filiere: str) -> Listable:
        if "MATH" in filiere:
            return Option.MATH

        if (
            "VIE" in filiere
            or "TERRE" in filiere
            or "PHYSIQUE" in filiere
            or "EXPERIMENTAL" in filiere
        ):
            return Option.EXP

        if "ECONOMIE" in filiere or "GESTION" in filiere:
            return Option.ECO


class MDL(Listable):
    SPSS = auto()
    PYTHON = auto()
    R = auto()
    POWER_BI = auto()
    AUTRE = auto()

    @classmethod
    def classify(self, logiciel: str) -> Listable:
        for software in self.get():
            if software.replace("_", " ") in logiciel:
                return self[software].name
        return self.AUTRE.name


# Importation des données
with open(file="data.csv", mode="r") as file:
    file = reader(file)
    headers = next(file)

    # Création de variables / TODO : avoid duplicates
    doc.add_heading("Variables")
    doc_headers = []

    for i, header in enumerate(headers):
        normalized_header = re.sub(r"\(.*?\)", "", normalize(header)).strip()
        words = normalized_header.split()

        if len(words) > 1:
            formatted_header = "".join(
                word[0].upper()
                + (word[1] if len(word) > 1 and word[1].isdigit() else "")
                for word in words
                if word
            )
        else:
            formatted_header = normalized_header.upper()

        doc_headers.append(f"`{formatted_header}` -> {header}")
        headers[i] = formatted_header

    # Documenter les variables
    doc.add_unordered_list(doc_headers)

    # Suppression des données sensibles et/ou inutiles
    for i in ["ND", "AD", "HORODATEUR"]:
        index = headers.index(i)
        headers.pop(index)
        file = [row[:index] + row[index + 1 :] for row in file]

    # Données numériques
    age_index = headers.index("AGE")
    annee_bac_index = headers.index("ADDB")
    # Données alphanumériques
    sex_dict = StoreCollection(headers.index("GENRE"))
    studyfield_dict = StoreCollection(headers.index("FD"))
    city_dict = StoreCollection(headers.index("VD"))
    mentionbac_dict = StoreCollection(headers.index("MB"))
    optionbac_dict = StoreCollection(headers.index("OB"))
    mentions_dicts = [StoreCollection(headers.index(f"MS{i}")) for i in range(1, 6)]
    excel_dict = StoreCollection(headers.index("UD"))
    logiciels_dict = StoreCollection(headers.index("MDL"))

    valid_years = []

    # Gestion des données manquantes
    ## Méthode 1 - Suppression des valeurs manquantes
    ### Critère global: Si les données manquantes est faible < 5%
    missing_values = sum(
        1 for row in file for data in row if data is None or data.strip() == ""
    )

    total_values = sum(len(row) for row in file)
    applicable = ((missing_values / total_values) * 100) < 5

    i = 0
    rows = list(file)
    while i < len(rows):
        row = rows[i]

        ### Critère variable: Si une des variables a plus de 30-40% de données manquantes
        nb_missing = sum(1 for data in row if data is None or data.strip() == "")
        percent = (nb_missing / len(row)) * 100
        too_many_missing_data = percent >= 30 and percent <= 40
        threshold = 0.5  # près de 1 = fortement corrélé

        if applicable:
            if too_many_missing_data:
                headers.pop(i)
                rows.pop(i)
                continue

        # TODO: implémenter l'imputation multiple

        # ✅ L'âge de l'étudiant

        def valid_age(value: int, threshold=24) -> str:
            if value <= threshold:
                return str(value)

            valid_ages = [numeric_data(data[age_index]) for data in rows]
            valid_ages = [
                age for age in valid_ages if age is not None and age <= threshold
            ]

            return str(max(valid_ages)) if valid_ages else str(threshold)

        age = (row[age_index] or "").strip()

        if not age:
            ### Régression linéaire
            ages = [int(data[age_index]) for data in rows]
            if correlation(ages) >= threshold:
                row[age_index] = str(predict_missing_value(ages)[i])
            else:  ### Moyenne
                avg_age = sum(int(data[age_index]) for data in rows) / len(rows)
                row[age_index] = str(round(avg_age))

            age = row[age_index].strip()

        current = numeric_data(age)
        if current is not None:
            row[age_index] = valid_age(current)
        else:
            raise ValueError("L'âge n'est pas correctement formatté")

        for dict in [
            sex_dict,
            studyfield_dict,
            excel_dict,
            *mentions_dicts,
        ]:
            dict.subscribe(row[dict.pos])

        city_dict.subscribe(row[city_dict.pos], approx=True)

        mention = re.sub(r"[. ]*", "", row[mentionbac_dict.pos])
        mentionbac_dict.subscribe(mention)

        match = re.search(r"(\d{4})[-/_\s]*(\d{4})?", row[annee_bac_index])
        if match:
            valid_years.append(match.group(2) if match.group(2) else match.group(1))
        else:
            valid_years.append(Counter(valid_years).most_common(1)[0][0])

        branche = Option.classify(normalize(row[optionbac_dict.pos]).upper())
        optionbac_dict.subscribe(branche.name, exact=True, format=False)

        logiciel = normalize(row[logiciels_dict.pos]).upper()
        possible_values = logiciels_dict.in_depth(logiciel)
        for possible_value in possible_values:
            logiciels_dict.subscribe(MDL.classify(possible_value), exact=True)

        i += 1

    doc.dump("README")  # Générer la documentation en markdown
