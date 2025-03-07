from typing import Callable
from unicodedata import normalize as normalize_unicode
from collections import deque
from csv import reader
from enum import Enum, auto

import re
import snakemd  # type: ignore
from datetime import datetime

doc = snakemd.Document()
stats = snakemd.Document()
time_generated = datetime.now().strftime("%d/%m/%Y %H:%M")
for markdown in [doc, stats]:
    markdown.add_heading(f"Analyse des données - Généré le {time_generated}")

# TODO: doc.doc.add_table_of_contents()


class Listable(Enum):
    @classmethod
    def get(cls) -> list[str]:
        return [c.name for c in cls]


def normalize(value: str) -> str:
    return (
        normalize_unicode("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    )


class UnwantedDataType(Enum):
    UNKNOWN = "Inconnu"
    MISSING = "Manquant"
    DUPLICATE = "Doublon"
    OUT_OF_RANGE = "Hors de portée"
    INVALID_FORMAT = "Format invalide"


class DataManager:
    def __init__(self):
        self.name = None
        self.TRESHOLD_CORRELATION = 0.5
        self.invalid_subsets = []

    def is_unknown(self, value) -> bool:
        return value == "N.V" or not value

    def is_applicable(self) -> bool:
        total_values = sum(len(row) for row in file)
        missing_data = (len(self.invalid_subsets) / total_values) * 100
        return missing_data < 5

    def removable(self, dict) -> bool:
        percent = (len(self.invalid_subsets) / len(dict.data.values())) * 100
        return self.is_applicable() and 30 <= percent <= 40

    # TODO : imputation multiple (>10%)
    def handle_missing_data(self, dict):
        if isinstance(dict, StoreSet):
            values = [subset["unresolved_value"] for subset in self.invalid_subsets]

            # Hypothèse de linéarité pour appliquer la régression
            if dict.correlation(values) > self.TRESHOLD_CORRELATION:
                self.data = dict.estimate_missing_values(values)
            else:  # Moyenne des valeurs connues
                for k in range(len(dict.data)):
                    if dict.data[k] is None:
                        dict.data[k] = int(round(sum(values) / len(values)))
        elif isinstance(dict, StoreCollection):
            return NotImplemented

    def generate_rapport(self, dict):
        stats.add_heading(f"Données invalides pour : {dict.name}", level=3)
        headers = [
            "",
            "",
            "Fréquence",
            "Pourcentage",
            "Pourcentage valide",
            "Pourcentage cumulé",
        ]

        valid_values = sum(set["count"] for set in dict.data.values())
        missing_values = len(dict.invalid_subsets)
        percent_missing_values = (
            missing_values / (valid_values + missing_values)
        ) * 100

        row = deque(
            [
                # Données valides
                [
                    "",
                    "Total",
                    valid_values,
                    "{filled}",
                    "{filled}",
                    "",
                ],
                # Données invalides
                [
                    "Manquant",
                    "Système",
                    missing_values,
                    f"{percent_missing_values:.2f}%",
                    "",
                    "",
                ],
                # Total des données
                [
                    "Total",
                    "",
                    missing_values + valid_values,
                    "{filled}",
                    "",
                    "",
                ],
            ]
        )

        cumul_percent = 0
        cumul_percent_valid = 0
        data_rows = []
        for k, data in list(enumerate(dict.data.values())):
            firs_row = k == min(dict.data.keys())
            percent_basedon_valid = data["count"] / (valid_values)
            percent_total = data["count"] / valid_values
            cumul_percent += percent_total
            cumul_percent_valid += percent_basedon_valid
            data_rows.append(
                [
                    "Valide" if firs_row else "",
                    data["name"],
                    data["count"],
                    f"{percent_total * 100:.2f}%",
                    f"{percent_basedon_valid * 100:.2f}%",
                    f"{cumul_percent * 100:.2f}%",
                ]
            )

        for item in reversed(data_rows):
            row.appendleft(item)

        percent_valid_values = (cumul_percent * 100) - percent_missing_values
        row[len(row) - 3][3] = f"{percent_valid_values:.2f}%"
        row[len(row) - 1][3] = f"{percent_valid_values + percent_missing_values:.2f}%"

        row[len(row) - 3][4] = f"{cumul_percent_valid * 100:.2f}%"

        stats.add_table(headers, list(row))

    def __handle_unresolved__(self, callback: Callable, value, type):
        if type != UnwantedDataType.MISSING:
            callback(value)

        return self.invalid_subsets.append(
            {"var_name": self.name, "unresolved_value": value, "type": type}
        )


class StoreCollection(DataManager):
    def __init__(self, pos):
        self.pos = pos
        self.data = {}
        self.name = doc_headers[pos]["default"] + f" ({doc_headers[pos]['format']})"
        self.invalid_subsets = []

    def is_unknown(self, value) -> bool:
        alnum = bool(re.search(r"[a-zA-Z0-9]", value.replace(" ", "")))
        return super().is_unknown(value) or not alnum

    def in_depth(self, value: str):
        match = re.search(r"[;,/]| ET ", value)
        matches = []

        if match:
            for v in value.split(match.group()):
                if not self.is_unknown(v):
                    matches.append(v)
            matches.append(value)
            return matches
        matches.append(value)
        return matches

    def subscribe(
        self, value: str | None, approx=False, exact=False, format=True, depth=True
    ):
        value = normalize(value).upper() if format and value else value

        def __subscribe__(v):
            self.data[len(self.data)] = v

        if not value or self.is_unknown(value):
            return self.__handle_unresolved__(
                __subscribe__, value, UnwantedDataType.MISSING
            )

        possible_values = self.in_depth(value) if depth else [value]

        if len(possible_values) > 1:
            for possible_value in possible_values:
                self.subscribe(possible_value, approx, exact, format)

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


class StoreSet(DataManager):
    def __init__(self, pos):
        self.pos = pos
        self.data = []
        self.name = doc_headers[pos]["default"] + f" ({doc_headers[pos]['format']})"
        self.invalid_subsets = []

    def collect(self, value: int | str | None, condition: Callable):
        value = value.strip() if isinstance(value, str) else value

        def __collect__(v):
            self.data.append(v)

        if self.is_unknown(value):
            return self.__handle_unresolved__(
                __collect__, value, UnwantedDataType.MISSING
            )

        if isinstance(value, int):
            if condition(value):
                return self.data.append(value)
            else:
                self.__handle_unresolved__(
                    __collect__, value, UnwantedDataType.OUT_OF_RANGE
                )
        elif isinstance(value, str):
            if match := re.search(r"(\d+)", value):
                value = int(match.group(1))
                if condition(value):
                    return self.data.append(value)
                else:
                    self.__handle_unresolved__(
                        __collect__, value, UnwantedDataType.OUT_OF_RANGE
                    )
            else:
                self.__handle_unresolved__(
                    __collect__, match, UnwantedDataType.INVALID_FORMAT
                )
        else:
            self.__handle_unresolved__(__collect__, value, UnwantedDataType.UNKNOWN)

    # Référence: https://fr.wikipedia.org/wiki/Corr%C3%A9lation_(statistiques)
    def correlation(self, data: list[int]) -> int:
        # X : Indices des valeurs connues, y : Valeurs connues
        X = [i for i, x in enumerate(data) if x is not None]
        y = [x for x in data if x is not None]

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

        return abs(numerator / denominator) if denominator != 0 else 0

    def estimate_missing_values(self, values: list[int]) -> list[int]:
        missing_indices = [i for i, x in enumerate(values) if x is None]

        # X : Indices des valeurs connues, y : Valeurs connues
        X = [i for i, x in enumerate(values) if x is not None]
        y = [x for x in values if x is not None]

        n = len(X)
        sum_x = sum(X)
        sum_y = sum(y)
        sum_xy = sum(x * y for x, y in zip(X, y))
        sum_x2 = sum(x**2 for x in X)

        a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x**2)
        b = (sum_y - a * sum_x) / n

        for i in missing_indices:
            values[i] = round(a * i + b)  # y = ax + b

        return values


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


class Option(Listable):
    ECO = EXP = MATH = auto()

    @classmethod
    def classify(cls, filiere: str):
        if "MATH" in filiere:
            return Option.MATH.name

        if (
            "VIE" in filiere
            or "TERRE" in filiere
            or "PHYSIQUE" in filiere
            or "EXPERIMENTAL" in filiere
        ):
            return Option.EXP.name

        if "ECONOMIE" in filiere or "GESTION" in filiere:
            return Option.ECO.name


class MDL(Listable):
    SPSS = PYTHON = R = POWER_BI = AUTRE = auto()

    @classmethod
    def classify(cls, logiciel: str):
        for software in cls.get():
            if software.replace("_", " ") in logiciel:
                return cls[software].name
        return cls.AUTRE.name


# Importation des données
with open(file="data.csv", mode="r") as file:
    file = reader(file)
    headers, doc_headers = next(file), []

    # Création des variables / TODO : avoid duplicates
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

        doc_headers.append({"format": formatted_header, "default": header})
        headers[i] = formatted_header

    # Suppression des données sensibles et/ou inutiles
    for i in ["ND", "AD", "HORODATEUR"]:
        index = headers.index(i)
        headers.pop(index)
        doc_headers.pop(index)
        file = [row[:index] + row[index + 1 :] for row in file]

    # Données numériques
    ages_set = StoreSet(headers.index("AGE"))
    anneebac_set = StoreSet(headers.index("ADDB"))
    ndfelsca_set = StoreSet(headers.index("NDFELSCA"))
    # Données alphanumériques
    sex_dict = StoreCollection(headers.index("GENRE"))
    studyfield_dict = StoreCollection(headers.index("FD"))
    city_dict = StoreCollection(headers.index("VD"))
    mentionbac_dict = StoreCollection(headers.index("MB"))
    optionbac_dict = StoreCollection(headers.index("OB"))
    mentions_dicts = [StoreCollection(headers.index(f"MS{i}")) for i in range(1, 6)]
    excel_dict = StoreCollection(headers.index("UD"))
    logiciels_dict = StoreCollection(headers.index("MDL"))
    padpa_dict = StoreCollection(headers.index("PADPA"))
    nddps_dict = StoreCollection(headers.index("NDDPS"))

    dicts = {
        "literal": [sex_dict, studyfield_dict, excel_dict, *mentions_dicts],
    }

    i = 0
    rows = list(file)

    while i < len(rows):
        ages_set.collect(rows[i][ages_set.pos], lambda age: 18 <= age <= 24)

        for dict in dicts["literal"]:
            dict.subscribe(rows[i][dict.pos])

        city_dict.subscribe(rows[i][city_dict.pos], approx=True, depth=False)

        mention = re.sub(r"[. ]*", "", rows[i][mentionbac_dict.pos])
        mentionbac_dict.subscribe(mention)

        match = re.search(r"(\d{4})[-/_\s]*(\d{4})?", rows[i][anneebac_set.pos])
        anneebac_set.collect(
            match.group(1) if match else None, lambda year: 2020 <= year <= 2023
        )

        branche = Option.classify(normalize(rows[i][optionbac_dict.pos]).upper())
        optionbac_dict.subscribe(branche, exact=True, format=False)

        logiciel = normalize(rows[i][logiciels_dict.pos]).upper()
        for value in logiciels_dict.in_depth(logiciel):
            logiciels_dict.subscribe(MDL.classify(value), exact=True, format=False)

        padpa_dict.subscribe(rows[i][padpa_dict.pos], exact=True)

        i += 1

        if i == len(rows):
            stats.add_heading("Statistiques", level=2)
            rows = [["N", "Valide"], ["", "Manquant"]]
            headers = [
                "",
                "",
                *[
                    d.name
                    for k in dicts
                    for d in dicts[k]
                    if len(d.invalid_subsets) > 0
                ],
            ]

            for dict in [
                d for k in dicts for d in dicts[k] if len(d.invalid_subsets) > 0
            ]:
                rows[0].append(str(len(dict.data)))
                rows[1].append(str(len(dict.invalid_subsets)))

            stats.add_table(headers, rows)

            stats.add_heading("Validation des données", level=2)
            for dict in [d for k in dicts for d in dicts[k]]:
                if len(dict.invalid_subsets) == 0:
                    continue

                if any(
                    subset["type"] == UnwantedDataType.MISSING
                    for subset in dict.invalid_subsets
                ):
                    dict.generate_rapport(dict)

                if dict.removable(dict):
                    headers.pop(i)
                    rows.pop(i)
                else:
                    dict.handle_missing_data(dict)

    # TODO : Interprétations et représentations graphiques
    stats.add_heading("Analyse des données", level=2)

    doc.add_heading("Variables", level=2)
    doc.add_unordered_list(
        [
            doc_headers[k]["default"] + f" -> {doc_headers[k]['format']}"
            for k, _ in enumerate(doc_headers)
        ]
    )

    # Généres la documentation et les statistiques en markdown
    doc.dump("DOCS")
    stats.dump("STATS")
