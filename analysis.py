from statistics import correlation, linear_regression, mean, median, stdev
from scipy.stats import shapiro, kstest
from snakemd import Document, Quote

from csv import reader
from re import search, split, sub
from typing import Callable, Literal
from enum import Enum, auto
from collections import deque
from datetime import datetime

from utils import matches_approx, normalize


doc = Document()
stats = Document()
MD_DIR = "markdown"
time_generated = datetime.now().strftime("%d/%m/%Y à %H:%M")
for markdown in [doc, stats]:
    markdown.add_heading(f"Analyse des données - Généré le {time_generated}")

# TODO: doc.add_table_of_contents()


class Listable(Enum):
    @classmethod
    def get(cls) -> list[str]:
        return [c.name for c in cls]


class UnwantedDataType(Listable):
    UNKNOWN = "Inconnu"
    MISSING = "Manquant"
    OUT_OF_RANGE = "Hors de portée"
    INVALID_FORMAT = "Format invalide"


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
    SPSS = auto()
    PYTHON = auto()
    R = auto()
    POWER_BI = auto()
    AUTRE = auto()

    @classmethod
    def classify(cls, logiciel: str):
        for software in cls.get():
            if matches_approx(software, logiciel):
                return cls[software].name
        return cls.AUTRE.name


class DataManager:
    def __init__(self):
        self.name = None
        self.invalid_subsets = []

    def is_unknown(self, value) -> bool:
        return value in ["N.V", "UNKNOWN"] or not value

    def is_applicable(self) -> bool:
        total_values = sum(len(row) for row in file)
        missing_data = (len(self.invalid_subsets) / total_values) * 100
        return missing_data < 5

    def removable(self, dict) -> bool:
        percent = (len(self.invalid_subsets) / dict.length()) * 100
        return self.is_applicable() and 30 <= percent <= 40

    def handle_missing_data(self, dict):
        if isinstance(dict, StoreSet):
            X = [i for i, x in enumerate(dict.data) if x is not None]  # Indices VC
            y = [x for x in dict.data if x is not None]  # VC

            has_oor = any(
                x
                for x in dict.invalid_subsets
                if x["type"] == UnwantedDataType.OUT_OF_RANGE
            )

            # Régression linéaire (Hypothèse de linéarité)
            if abs(correlation(X, y)) > 0.5:
                slope, intercept = linear_regression(X, y)
                for i, value in enumerate(dict.data):
                    if value is None:
                        dict.data[i] = slope * i + intercept  # y = ax + b
            else:  # Moyenne et Médiane
                for k in range(len(dict.data)):
                    if dict.data[k] is None:
                        dict.data[k] = (
                            int(round(sum(y) / len(y))) if not has_oor else median(y)
                        )

        # Mode (VF)
        elif isinstance(dict, StoreCollection):
            none_indices = [k for k, v in dict.data.items() if v is None]
            valid_data = [v for v in dict.data.values() if v is not None]
            common_value = max(valid_data, key=lambda x: x["count"])
            common_value["count"] += len(none_indices)
            # for index in sorted(none_indices, reverse=True):
            #     dict.data.pop(index)
            # if index < len(self.invalid_subsets):
            #     self.invalid_subsets.pop(index)

    def generate_rapport(self, dict):
        stats.add_heading(f"{dict.name["default"]} [{dict.name["format"]}]", level=4)
        headers = [
            "",
            "",
            "Fréquence",
            "Pourcentage",
            "Pourcentage valide",
            "Pourcentage cumulé",
        ]

        missing_values = len(dict.invalid_subsets)
        valid_values = (
            dict.length() if isinstance(dict, StoreCollection) else len(dict.data)
        )

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
                    "{percent_values}",
                    "{percent_valid_values}",
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
                    "{percent_values}",
                    "",
                    "",
                ],
            ]
        )

        cumul_percent = 0
        cumul_percent_valid = 0
        data_rows = []
        first_row = True
        stores = (
            dict.data.values()
            if isinstance(dict, StoreCollection)
            else list(set(dict.data))
        )

        for k, data in enumerate(stores):
            if data is None:
                continue

            if isinstance(dict, StoreCollection):
                count = data["count"]
                name = data["name"]
            else:
                count = dict.data.count(data)
                name = data

            percent_total = count / (valid_values + missing_values)
            percent_basedon_valid = count / valid_values

            cumul_percent += percent_total
            cumul_percent_valid += percent_basedon_valid

            data_rows.append(
                [
                    "Valide" if first_row else "",
                    name,
                    count,
                    f"{percent_total * 100:.2f}%",
                    f"{percent_basedon_valid * 100:.2f}%",
                    f"{cumul_percent_valid * 100:.2f}%",
                ]
            )

            first_row = False

        for item in reversed(data_rows):
            row.appendleft(item)

        percent_valid_values = (cumul_percent_valid * 100) - percent_missing_values

        row[len(row) - 3][3] = f"{cumul_percent * 100:.2f}%"
        row[len(row) - 3][4] = f"{cumul_percent_valid * 100:.2f}%"
        row[len(row) - 1][3] = f"{percent_valid_values + percent_missing_values:.2f}%"

        stats.add_table(headers, [[str(cell) for cell in r] for r in row])

    def generate_statistics(self, dict):
        stats.add_heading(f"{dict.name["default"]} [{dict.name["format"]}]", level=3)
        if isinstance(dict, StoreSet):
            headers = ["", "N", "Minimum", "Maximum", "Moyenne", "Ecart type"]

            avg = round(mean(dict.data), 3)
            std_dev = round(stdev(dict.data), 3)

            rows = [
                [
                    "N Valide (liste)",
                    len(dict.data),
                    max(dict.data),
                    min(dict.data),
                    avg,
                    std_dev,
                ]
            ]

            stats.add_table(headers, rows)

            def interpretation(*args: str):
                stats.add_block(
                    Quote(
                        f"L'écart-type est relativement {args[0]} ce qui veut dire {args[1]}"
                    )
                )

            if (std_dev / avg) * 100 > 50:
                interpretation("élevé", "qu'il y a une grande dispersion des données")
            else:
                interpretation("faible", "que les valeurs sont proches de la moyenne")

            stats.add_heading("Distribution des données et test de normalité", level=4)

            headers = ["Kolmogrov-Smirnov", "Shapiro-Wilk"]
            sub_header = ["Statistiques", "ddl", "Sig."]
            header_styles = "style='text-align: center;' colspan='3'"

            kolmogrov_dn, kolmogrov_pvalue = kstest(dict.data, "norm")
            shapiro_dn, shapiro_pvalue = shapiro(dict.data)

            html_table = f"""
    <table>
        <tr>
            {"".join(f"<th {header_styles}>{header}</th>" for header in headers)}
        </tr>
        <tr>
            {"".join(f"<th>{header}</th>" for header in sub_header * 2)}
        </tr>
        <tr>
            <td>{kolmogrov_dn}</td>
            <td>{len(dict.data)}</td>
            <td>{kolmogrov_pvalue}</td>
            <td>{shapiro_dn}</td>
            <td>{len(dict.data)}</td>
            <td>{shapiro_pvalue}</td>
        </tr>
    </table>
    """

            stats.add_raw(html_table)

            def interpretation_normality(*args: str):
                stats.add_block(Quote(f"Une distribution {args[0]}"))

            if shapiro_pvalue > 0.05:
                interpretation_normality("normale")
            else:
                interpretation_normality("non normale")
        else:
            headers = [
                "",
                "",
                "Fréquence",
                "Pourcentage",
                "Pourcentage valide",
                "Pourcentage cumulé",
            ]

            # values = sum(set["count"] for set in dict.data.values())

            row = [
                [
                    "Valide",
                    "",
                    "{filled}",
                    "{filled}",
                    "{filled}",
                    "",
                ],
            ]

            """ cumul_percent = 0
            for k, data in enumerate(dict.data):
                print(k, data)
                cumul_percent += data["count"] / values
                row.append(
                    [
                        "",
                        data.name,
                        data.count,
                        data.count / values,  # filter valid values
                        cumul_percent,
                    ]
                ) """

            row.append(
                [
                    "",
                    "Total",
                    "{filled}",
                    "{totalvaluespercent}",
                    "{totalvaluespercentvalid}",
                    "",
                ]
            )

            # TODO : Tableaux croisés
            stats.add_heading("Tableau croisé", level=4)

            # TODO : Test de Khi-carré
            stats.add_heading("Test de Khi-carré", level=4)
            headers = ["", "Valeur", "dll", "Sig."]

            p_cor = abs(
                correlation(
                    [i for i, x in enumerate(dict.data) if x is not None],
                    [x for x in dict.data if x is not None],
                )
            )

            rows = [
                ["Khi-Carré de Pearson", p_cor, 2, 0.565],
                ["Rapport de vraisemblance", 1.530, 2, 0.465],
                ["N d'observations valides", 20, "", ""],
            ]

            p = 0  # coef de corr ?

            stats.add_table(headers, rows)

            if p < 0.05:
                stats.add_block(
                    Quote("Il y a une relation significative entre les variables")
                )

    # TODO : Interprétations et représentations graphiques
    def visualize(self, dict):
        return NotImplemented
        # histogrammes (distribution des variables quantitatives)
        # boxplot (détection des valeurs aberrantes)
        # diagramme en barres (variables catégorielles)
        # nuage de points (Scatterplot) (relation entre 2 variables quantitatives)

    # TODO: Analyse inférentielle
    def analyze(self, dict):
        return NotImplemented


class StoreCollection(DataManager):
    def __init__(
        self, pos, method: Literal["exact", "approx"] = "exact", recursive=False
    ):
        self.pos = pos
        self.data = {}
        self.method = method
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.recursive = recursive

    def is_unknown(self, value: str) -> bool:
        alnum = search(r"[a-zA-Z0-9]", value.strip())
        return DataManager.is_unknown(self, value) or not alnum

    def in_depth(self, value: str):
        parts = split(r"[;,/]| ET ", value)
        matches = []

        for v in parts:
            if not self.is_unknown(v.strip()):
                matches.append(v.strip())

        return matches

    def subscribe(self, value: str | None):
        value = normalize(value).upper() if value else value

        if not value or self.is_unknown(value):
            self.data[len(self.data)] = None
            return self.invalid_subsets.append(
                {
                    "var_name": self.name,
                    "unresolved_value": value,
                    "pos": len(self.data),
                    "type": type,
                }
            )

        if self.recursive and len(possible_values := self.in_depth(value)) > 1:
            for p_value in possible_values:
                self.subscribe(p_value)
            return

        for key, info in self.data.items():
            if info is None:
                continue
            if self.method == "approx" and matches_approx(value, info["name"]):
                self.data[key]["count"] += 1
                return
            elif self.method == "exact" and info["name"] == value:
                self.data[key]["count"] += 1
                return
            elif self.method != "exact" and (
                info["name"] in value or value in info["name"]
            ):
                self.data[key]["count"] += 1
                return
        self.data[len(self.data)] = {"name": value, "count": 1}

    def length(self):
        return sum(item["count"] for item in self.data.values() if item is not None)


class StoreSet(DataManager):
    def __init__(self, pos, rule: Callable | None = None):
        self.pos = pos
        self.data = []
        self.rule = rule
        self.name = doc_headers[pos]
        self.invalid_subsets = []

    def collect(self, value: int | str | None):
        value = value.strip() if isinstance(value, str) else value

        def unresolved(v, type):
            self.data.append(None)
            self.invalid_subsets.append(
                {
                    "var_name": self.name,
                    "unresolved_value": v,
                    "pos": len(self.data),
                    "type": type,
                }
            )

        def satifies_rule(v, unexpected_type):
            if self.rule is not None:
                if self.rule(value):
                    return self.data.append(value)
                else:
                    return unresolved(v, unexpected_type)
            else:
                return self.data.append(value)

        if self.is_unknown(value):
            return unresolved(value, UnwantedDataType.MISSING)

        if isinstance(value, int):
            return satifies_rule(value, UnwantedDataType.OUT_OF_RANGE)
        elif isinstance(value, str):
            if match := search(r"(\d+)", value):
                value = int(match.group(1))
                return satifies_rule(value, UnwantedDataType.OUT_OF_RANGE)
            else:
                unresolved(match, UnwantedDataType.INVALID_FORMAT)
        else:
            unresolved(value, UnwantedDataType.UNKNOWN)

    def length(self):
        return len([item for item in self.data if item is not None])


# Importation des données
with open(file="data.csv", mode="r", encoding="utf-8") as file:
    file = reader(file)
    headers, doc_headers = next(file), []

    # Création des variables
    for i, header in enumerate(headers):
        normalized_header = sub(r"\(.*?\)", "", normalize(header)).strip()
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

        # TODO : avoid duplicates
        if formatted_header in headers:
            NotImplemented  # type: ignore

        doc_headers.append({"format": formatted_header, "default": header})
        headers[i] = formatted_header

    # Suppression des données sensibles et/ou inutiles
    for i in ["ND", "AD", "HORODATEUR"]:
        index = headers.index(i)
        headers.pop(index)
        doc_headers.pop(index)
        file = [row[:index] + row[index + 1 :] for row in file]

    # Traitement des données numériques et alphanumériques
    ages_set = StoreSet(headers.index("AGE"), lambda age: 18 <= age <= 24)
    city_dict = StoreCollection(headers.index("VD"), method="approx")
    mentions_dicts = [StoreCollection(headers.index(f"MS{i}")) for i in range(1, 6)]
    mentionbac_dict = StoreCollection(headers.index("MB"))
    padpa_dict = StoreCollection(headers.index("PADPA"))
    sex_dict = StoreCollection(headers.index("GENRE"))
    anneebac_set = StoreSet(headers.index("ADDB"), lambda year: 2020 <= year <= 2023)
    ndfelsca_dict = StoreSet(headers.index("NDFELSCA"))
    studyfield_dict = StoreCollection(headers.index("FD"), method="approx")
    optionbac_dict = StoreCollection(headers.index("OB"))
    excel_dict = StoreCollection(headers.index("UD"))
    logiciels_dict = StoreCollection(headers.index("MDL"), recursive=True)
    nddps_dict = StoreSet(headers.index("NDDPS"))
    tdl_dict = StoreCollection(headers.index("TDL"), method="approx")
    preferedsubjct_dict = StoreCollection(
        headers.index("MP"), method="approx", recursive=True
    )
    tpslepj_dict = StoreCollection(headers.index("TPSLEPJ"))
    mdvu_dict = StoreCollection(headers.index("MDVU"))
    cdfvvpa_dict = StoreCollection(headers.index("CDFVVPA"))
    caepm_dict = StoreCollection(headers.index("CAEPM"))
    nddtps_dict = StoreCollection(headers.index("NDDTPS"))
    tepde_dict = StoreCollection(headers.index("TEPDE"))
    spdr_dict = StoreCollection(headers.index("SPDR"), recursive=True)
    qds_dict = StoreSet(headers.index("QDS"))
    # lambda salaire: 1000 <= salaire <= 20000
    dmm_dict = StoreSet(headers.index("DMM"))
    lp_dict = StoreCollection(headers.index("LP"))
    ndllpa_dict = StoreCollection(headers.index("NDLLPA"))
    tdsp_dict = StoreCollection(headers.index("TDSP"), method="approx", recursive=True)
    ap_dict = StoreCollection(headers.index("AP"))  # ❌ (Unstable)
    nmddspn_dict = StoreCollection(headers.index("NMDDSPN"))  # ✅
    ndpsynps_dict = StoreCollection(headers.index("NDPSYNPS"))  # ✅
    pdmlde_dict = StoreCollection(headers.index("PDMLDE"))  # ✅
    tdlpu_dict = StoreCollection(headers.index("TDLPU"), recursive=True)  # ✅
    fddrspj_dict = StoreCollection(headers.index("FDDRSPJ"))  # ✅

    dicts = [
        sex_dict,
        tdlpu_dict,
        pdmlde_dict,
        fddrspj_dict,
        qds_dict,
        ndllpa_dict,
        tdsp_dict,
        ap_dict,
        lp_dict,
        tepde_dict,
        optionbac_dict,
        ndpsynps_dict,
        nmddspn_dict,
        mentionbac_dict,
        nddtps_dict,
        cdfvvpa_dict,
        tpslepj_dict,
        mdvu_dict,
        caepm_dict,
        city_dict,
        dmm_dict,
        ndfelsca_dict,
        preferedsubjct_dict,
        studyfield_dict,
        spdr_dict,
        logiciels_dict,
        tdl_dict,
        nddps_dict,
        padpa_dict,
        excel_dict,
        ages_set,
        anneebac_set,
        *mentions_dicts,
    ]

    unprocessed_data = [
        f"`{h["format"]}` > {h["default"]}"
        for h in doc_headers
        if h["format"] not in {d.name["format"] for d in dicts}
    ]
    if len(unprocessed_data) >= 1:
        doc.add_heading("Variables à traité", level=1)
        doc.add_ordered_list(unprocessed_data)

    i = 0
    rows = list(file)

    while i < len(rows):

        for dict in dicts:
            if dict not in [anneebac_set, optionbac_dict, logiciels_dict]:
                if isinstance(dict, StoreCollection):
                    dict.subscribe(rows[i][dict.pos])
                elif isinstance(dict, StoreSet):
                    dict.collect(rows[i][dict.pos])

        match = search(r"(\d{4})[-/_\s]*(\d{4})?", rows[i][anneebac_set.pos])
        year = match.group(2) if match and match.group(2) else match and match.group(1)
        anneebac_set.collect(year)

        branche = Option.classify(normalize(rows[i][optionbac_dict.pos]).upper())
        optionbac_dict.subscribe(branche)

        logiciel = normalize(rows[i][logiciels_dict.pos]).upper()
        unknown_logiciel = logiciels_dict.is_unknown(logiciel)
        for value in logiciels_dict.in_depth(logiciel):
            software = MDL.classify(value) if not unknown_logiciel else None
            logiciels_dict.subscribe(software)

        i += 1

    stats.add_heading("Vue des variables", level=2)
    # TODO : Generate Variable View Table

    stats.add_heading("Gestion des données", level=2)

    stats.add_heading("Identification des données manquantes", level=3)
    rows = [["N", "VALIDE"], *[["", name] for name in UnwantedDataType.get()]]
    headers = [d.name["format"] for d in dicts]
    for dict in dicts:
        rows[0].append(str(dict.length()))
        for i, type in enumerate(UnwantedDataType.get()):
            subset = [
                v for v in dict.invalid_subsets if v["type"] == UnwantedDataType[type]
            ]
            rows[i + 1].append(str(len(subset)) if len(subset) != 0 else "")
    stats.add_table(["", "", *headers], rows)
    for dict in dicts:
        dict.generate_rapport(dict)

    stats.add_heading("Traitement des données manquantes", level=2)
    for dict in dicts:
        if dict.removable(dict):
            headers.pop(i)
            rows.pop(i)
            continue
        dict.handle_missing_data(dict)

    stats.add_heading("Statistiques descriptives", level=2)
    # for dict in dicts:
    #     dict.generate_statistics(dict)

    stats.add_heading("Visualisation/Représentation graphique", level=2)
    for dict in dicts:
        dict.visualize(dict)

    stats.add_heading("Analyse inférentielle", level=2)
    for dict in dicts:
        dict.analyze(dict)

    doc.add_heading("Codification des variables", level=2)
    doc.add_unordered_list(
        [
            f"`{doc_headers[k]["format"]}` -> {doc_headers[k]['default']}"
            for k, _ in enumerate(doc_headers)
        ]
    )

    doc.dump("DOCS", directory=MD_DIR)
    stats.dump("STATS", directory=MD_DIR)
