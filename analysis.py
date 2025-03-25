from statistics import correlation, linear_regression, median
from scipy.stats import chi2_contingency, shapiro, kstest, norm, chisquare
import matplotlib.pyplot as plt
import numpy as np
import snakemd as mkdn
import argparse

import re
import typing
import collections
import datetime
import enum
import csv

import utils


doc = mkdn.Document()
data = mkdn.Document()
stats = mkdn.Document()
MD_DIR = "markdown"
time_generated = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
for markdown in [doc, data, stats]:
    markdown.add_heading(f"Analyse des données - Généré le {time_generated}")


class Listable(enum.Enum):
    @classmethod
    def get(cls) -> list[str]:
        return [c.name for c in cls]


class UnwantedDataType(Listable):
    OUTLIER = "Valeur aberrante"
    MISSING = "Manquant"
    INVALID_FORMAT = "Format invalide"


class Option(Listable):
    ECO = enum.auto()
    EXP = enum.auto()
    MATH = enum.auto()

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
    SPSS = enum.auto()
    PYTHON = enum.auto()
    R = enum.auto()
    POWER_BI = enum.auto()
    AUTRE = enum.auto()

    @classmethod
    def classify(cls, logiciel: str):
        for software in cls.get():
            if utils.matches_approx(software, logiciel):
                return cls[software].name
        return cls.AUTRE.name


class NDDTPS():
    @classmethod
    def classify(cls, value: str):
        if "PAS" in value or "AUCUN" in value or "NON" in value or "RIEN" in value:
            return 0
        else:
            return value


class DataManager:
    def __init__(self):
        self.name = {}
        self.invalid_subsets = []

    def length(self) -> int:
        raise NotImplementedError("Subclasses must implement the 'length' method")

    def is_unknown(self, value) -> bool:
        return value in ["N.V", "UNKNOWN"] or value is None

    def is_applicable(self) -> bool:
        total_values = sum(len(row) for row in file)
        missing_data = (len(self.invalid_subsets) / total_values) * 100
        return missing_data < 5

    def removable(self) -> bool:
        percent = (len(self.invalid_subsets) / self.length()) * 100
        return self.is_applicable() and 30 <= percent <= 40

    #  Interquartile Range (IQR)
    def outliers(self, data: list[int]) -> list[int]:
        q1 = np.quantile(data, 0.25)
        q3 = np.quantile(data, 0.75)
        iqr_region = q3 - q1
        upper_bound = q3 + (1.5 * iqr_region)
        lower_bound = q1 - (1.5 * iqr_region)
        array = np.array(data)
        outliers = array[(array <= lower_bound) | (array >= upper_bound)]
        return list(map(int, outliers))

    def handle_outliers(self):
        filename = f"assets/boxplot_{dict.name["format"]}.png"

        bp = plt.boxplot(dict.data)
        median = bp["medians"][0].get_ydata()[0]

        plt.figure(figsize=(10, 6))
        plt.boxplot(dict.data, vert=True, patch_artist=True)
        plt.title(f"Boxplot : {self.name['default']}", fontsize=14)
        plt.ylabel("Valeurs", fontsize=12)
        plt.grid(axis="y", alpha=0.75)
        plt.legend(
            [bp["medians"][0], bp["boxes"][0]],
            [f"Médiane : {median}", "IQR"],
        )

        plt.savefig(filename, bbox_inches="tight")

        data.add_heading(f"{self.name["default"]} [{self.name["format"]}]", level=4)
        data.add_block(mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")]))

    # TODO : Kurtosis & Skewness
    def handle_missing_data(self, dict):
        if isinstance(dict, StoreSet):
            X = [i for i, x in enumerate(dict.data) if x is not None]  # Indices VC
            y = [x for x in dict.data if x is not None]  # VC

            outliers = dict.outliers(y)
            has_outliers = len(outliers) > 0

            for outlier in outliers:
                self.invalid_subsets.append({
                    "pos": dict.data.index(outlier),
                    "type": UnwantedDataType.OUTLIER,
                })

            # Régression linéaire (Hypothèse de linéarité)
            if abs(correlation(X, y)) > 0.5:
                slope, intercept = linear_regression(X, y)
                for i, value in enumerate(dict.data):
                    if value is None:
                        value = slope * i + intercept  # y = ax + b
                        dict.data[i] = value
                        data.add_paragraph(f"La valeur numérique manquante de la variable {dict.name["format"]} a été estimée à {value}")
            else:  # Moyenne/Médiane
                for k in range(len(dict.data)):
                    if dict.data[k] is None:
                        dict.data[k] = (median(y) if has_outliers else int(round(sum(y) / len(y))))

            if has_outliers:
                self.handle_outliers()

        # Mode (VF)
        elif isinstance(dict, StoreCollection):
            for k, v in list(dict.data.items()):
                if v is None:
                    valid_data = [v for v in dict.data.values() if v is not None]
                    common_value = max(valid_data, key=lambda x: x["count"])
                    common_value["count"] += 1
                    dict.data.pop(k)
                    self.invalid_subsets = [subset for subset in self.invalid_subsets if subset["pos"] != k]

    def generate_rapport(self, dict):
        data.add_heading(f"{dict.name["default"]} [{dict.name["format"]}]", level=4)
        headers = ["", "", "Fréquence", "Pourcentage", "Pourcentage valide", "Pourcentage cumulé"]

        missing_values = len(dict.invalid_subsets)
        valid_values = (dict.length() if isinstance(dict, StoreCollection) else len(dict.data))
        percent_missing_values = (missing_values / (valid_values + missing_values)) * 100

        row = collections.deque(
            [
                # Données valides
                ["", "Total", valid_values, "{percent_values}", "{percent_valid_values}", ""],
                # Données invalides
                ["Manquant", "Système", missing_values, f"{percent_missing_values:.2f}%", "", ""],
                # Total des données
                ["Total", "", missing_values + valid_values, "{percent_values}", "", ""],
            ]
        )

        cumul_percent = 0
        cumul_percent_valid = 0
        data_rows = []
        first_row = True
        stores = (dict.data.values() if isinstance(dict, StoreCollection) else list(set(dict.data)))

        for k, value in enumerate(stores):
            if value is None:
                continue

            if isinstance(dict, StoreCollection):
                count = value["count"]
                name = value["name"]
            else:
                count = dict.data.count(value)
                name = value

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

        data.add_table(headers, [[str(cell) for cell in r] for r in row])

    def generate_statistics(self, dict):
        stats.add_heading(f"{dict.name["default"]} [{dict.name["format"]}]", level=3)
        stats.add_heading("Dispersion des données", level=4)

        if isinstance(dict, StoreSet):
            headers = ["", "N", "Minimum", "Maximum", "Moyenne", "Écart type"]

            min = np.min(dict.data)
            max = np.max(dict.data)
            mean = np.mean(dict.data)
            std = np.std(dict.data, ddof=1)

            rows = [
                [
                    "N Valide (liste)",
                    len(dict.data),
                    min,
                    max,
                    round(mean, 4),
                    round(std, 4),
                ]
            ]

            stats.add_table(headers, rows)

            if std > max - min:
                message = f"L'écart-type est relativement élevé, ce qui veut dire qu'il y a une grande dispersion des données"
            else:
                message = f"L'écart-type est relativement faible, ce qui veut dire que les valeurs sont proches de la moyenne"

            stats.add_block(mkdn.Quote(message))

            stats.add_heading("Distribution des données et test de normalité", level=4)
            headers = ["Kolmogrov-Smirnov", "Shapiro-Wilk"]
            sub_header = ["Statistiques", "ddl", "Sig."]
            header_styles = "style='text-align: center;' colspan='3'"

            shapiro_dn, shapiro_pvalue = shapiro(dict.data)
            kolmogrov_dn, kolmogorov_pvalue = kstest(dict.data, "norm", args=(mean, std))

            html_table = f"""
<table>
    <tr>
        {"".join(f"<th {header_styles}>{header}</th>" for header in headers)}
    </tr>
    <tr>
        {"".join(f"<th>{header}</th>" for header in sub_header * 2)}
    </tr>
    <tr>
        <td>{round(kolmogrov_dn, 4)}</td>
        <td>{len(dict.data)}</td>
        <td>{round(kolmogorov_pvalue, 4)}</td>
        <td>{round(shapiro_dn, 4)}</td>
        <td>{len(dict.data)}</td>
        <td>{round(shapiro_pvalue, 4)}</td>
    </tr>
</table>
"""

            stats.add_raw(html_table)

            p_value = shapiro_pvalue if len(dict.data) < 50 else kolmogorov_pvalue
            sig = 0.05

            if p_value > sig:
                message = "Une distribution normale"
                filename = f"assets/hist_{dict.name["format"]}.png"

                x_ticks = [
                    mean - 3 * std,
                    mean - 2 * std,
                    mean - std,
                    mean,
                    mean + std,
                    mean + 2 * std,
                    mean + 3 * std,
                ]

                plt.figure(figsize=(8, 5))
                plt.hist(dict.data, bins=10, density=True, alpha=0.7, color="blue", edgecolor="black")

                x = np.linspace(min, max, 100)
                p = norm.pdf(x, mean, std)

                plt.xticks(x_ticks, labels=[
                    r"$\mu - 3\sigma$",
                    r"$\mu - 2\sigma$",
                    r"$\mu - \sigma$",
                    r"$\mu$",
                    r"$\mu + \sigma$",
                    r"$\mu + 2\sigma$",
                    r"$\mu + 3\sigma$"
                ])

                plt.plot(x, p, "r-", linewidth=2)
                plt.axvline(float(np.mean(dict.data)), ls="--", color="lightgray")
                plt.title(f"Histogramme avec une courbe de distribution normale")
                plt.xlabel(dict.name["default"])
                plt.ylabel("Probabilité de densité")
                plt.savefig(filename, bbox_inches="tight")

                stats.add_block(mkdn.Quote(message))
                stats.add_block(mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")]))
            else:
                stats.add_block(mkdn.Quote(message))
                message = "Une distribution non normale"

        else:
            stats.add_heading("Test de Khi-carré", level=4)
            headers = ["", "Valeur", "dll", "Sig."]

            observed = [dict.data[key]["count"] for key in dict.data]
            stat, p_value, dof, expected = chi2_contingency(observed)

            rows = [
                ["Khi-Carré de Pearson", 4, len(dict.data), 0.565],
                ["Rapport de vraisemblance", 1.530, 2, 0.465],
                ["N d'observations valides", p_value, None, None],
            ]

            p = 0  # coef de corr ?

            stats.add_table(headers, rows)

            if p < 0.05:
                stats.add_block(mkdn.Quote("Il y a une relation significative entre les variables"))

    # TODO: Analyse inférentielle
    def analyze(self, dict):
        return NotImplemented


class StoreCollection(DataManager):
    def __init__(self, pos, method: typing.Literal["exact", "approx"] = "exact", recursive=False, verified=False):
        self.pos = pos
        self.data = {}
        self.method = method
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.recursive = recursive
        self.verified = verified

    def in_depth(self, value: str):
        parts = re.split(r"[;,/]| ET ", value)
        matches = []

        for v in parts:
            matches.append(v.strip())

        return matches

    def subscribe(self, value: str | None):
        value = utils.normalize(value).upper() if value else value

        def unresolved(type):
            self.data[len(self.data)] = None
            self.invalid_subsets.append({
                "pos": len(self.data),
                "type": type,
            })

        if not value or self.is_unknown(value):
            return unresolved(UnwantedDataType.MISSING)
        elif value and not re.search(r"[a-zA-Z]", value.strip()) and not re.fullmatch(r"\d+(?:\s*-\s*\d+)?", value.strip()):
            return unresolved(UnwantedDataType.INVALID_FORMAT)

        if self.recursive and len(possible_values := self.in_depth(value)) > 1:
            for p_value in possible_values:
                self.subscribe(p_value)
            return

        for key, info in self.data.items():
            if info is None:
                continue
            if self.method == "approx" and utils.matches_approx(value, info["name"]):
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

    def length(self) -> int:
        return sum(item["count"] for item in self.data.values() if item is not None)


class StoreSet(DataManager):
    def __init__(self, pos, verified=False):
        self.pos = pos
        self.data = []
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.verified = verified

    def collect(self, value: int | str | None):
        value = value.strip() if isinstance(value, str) else value

        def unresolved(type):
            self.data.append(None)
            self.invalid_subsets.append({
                "pos": len(self.data),
                "type": type,
            })

        if self.is_unknown(value):
            return unresolved(UnwantedDataType.MISSING)

        if isinstance(value, int):
            return self.data.append(value)
        elif isinstance(value, str):
            if match := re.search(r"(\d+)", value):
                value = int(match.group(1))
                return self.data.append(value)
            else:
                unresolved(UnwantedDataType.INVALID_FORMAT)

    def length(self) -> int:
        return len([item for item in self.data if item is not None])


# Importation des données
with open(file="data.csv", mode="r", encoding="utf-8") as file:
    file = csv.reader(file)
    headers, doc_headers = next(file), []

    # Création des variables
    for i, header in enumerate(headers):
        normalized_header = re.sub(r"\(.*?\)", "", utils.normalize(header)).strip()
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

        if formatted_header in headers:
            formatted_header = f"{formatted_header}_{headers.count(formatted_header) + 1}"

        doc_headers.append({"format": formatted_header, "default": header})
        headers[i] = formatted_header

    # Suppression des données sensibles et/ou inutiles
    for i in ["ND", "AD", "HORODATEUR"]:
        index = headers.index(i)
        headers.pop(index)
        doc_headers.pop(index)
        file = [row[:index] + row[index + 1:] for row in file]

    # Traitement des données numériques et alphanumériques (catégorielles)
    ages_set = StoreSet(headers.index("AGE"), verified=True)
    city_dict = StoreCollection(headers.index("VD"), method="approx", verified=True)
    mentions_dicts = [StoreCollection(headers.index(f"MS{i}"), verified=True) for i in range(1, 6)]
    mentionbac_dict = StoreCollection(headers.index("MB"), verified=True)
    padpa_dict = StoreCollection(headers.index("PADPA"), verified=True)
    sex_dict = StoreCollection(headers.index("GENRE"), verified=True)
    anneebac_set = StoreSet(headers.index("ADDB"), verified=True)
    ndfelsca_dict = StoreSet(headers.index("NDFELSCA"), verified=True)
    studyfield_dict = StoreCollection(headers.index("FD"), method="approx", verified=True)
    optionbac_dict = StoreCollection(headers.index("OB"), verified=True)
    excel_dict = StoreCollection(headers.index("UD"), verified=True)
    logiciels_dict = StoreCollection(headers.index("MDL"), recursive=True, verified=True)
    nddps_dict = StoreSet(headers.index("NDDPS"), verified=True)
    tdl_dict = StoreCollection(headers.index("TDL"), method="approx", verified=True)
    mp_dict = StoreCollection(headers.index("MP"), method="approx", recursive=True, verified=True)
    tpslepj_dict = StoreCollection(headers.index("TPSLEPJ"), verified=True)
    mdvu_dict = StoreCollection(headers.index("MDVU"), method="approx", recursive=True, verified=True)
    cdfvvpa_dict = StoreSet(headers.index("CDFVVPA"), verified=True)
    caepm_dict = StoreSet(headers.index("CAEPM"), verified=True)
    nddtps_dict = StoreSet(headers.index("NDDTPS"), verified=False)
    tepde_dict = StoreCollection(headers.index("TEPDE"), verified=True)
    spdr_dict = StoreCollection(headers.index("SPDR"), recursive=True, verified=True)
    qds_dict = StoreSet(headers.index("QDS"), verified=True)
    dmm_dict = StoreSet(headers.index("DMM"), verified=True)
    lp_dict = StoreCollection(headers.index("LP"), recursive=True, verified=True)
    ndllpa_dict = StoreSet(headers.index("NDLLPA"), verified=True)
    tdsp_dict = StoreCollection(headers.index("TDSP"), method="approx", recursive=True, verified=True)
    ap_dict = StoreSet(headers.index("AP"), verified=True)
    nmddspn_dict = StoreSet(headers.index("NMDDSPN"), verified=True)
    ndpsynps_dict = StoreCollection(headers.index("NDPSYNPS"), verified=True)
    pdmlde_dict = StoreCollection(headers.index("PDMLDE"), verified=True)
    tdlpu_dict = StoreCollection(headers.index("TDLPU"), recursive=True, verified=True)
    fddrspj_dict = StoreCollection(headers.index("FDDRSPJ"), verified=True)

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
        mp_dict,
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

    i = 0
    rows = list(file)

    while i < len(rows):

        for dict in dicts:
            if dict not in [anneebac_set, optionbac_dict, logiciels_dict, nddtps_dict]:
                if isinstance(dict, StoreCollection):
                    dict.subscribe(rows[i][dict.pos])
                elif isinstance(dict, StoreSet):
                    dict.collect(rows[i][dict.pos])

        match = re.search(r"(\d{4})[-/_\s]*(\d{4})?", rows[i][anneebac_set.pos])
        year = match.group(2) if match and match.group(2) else match and match.group(1)
        anneebac_set.collect(year)

        nddtps = NDDTPS.classify(rows[i][nddtps_dict.pos].upper())
        nddtps_dict.collect(nddtps)

        branche = Option.classify(utils.normalize(rows[i][optionbac_dict.pos]).upper())
        optionbac_dict.subscribe(branche)

        logiciel = utils.normalize(rows[i][logiciels_dict.pos]).upper()
        unknown_logiciel = logiciels_dict.is_unknown(logiciel)
        for value in logiciels_dict.in_depth(logiciel):
            software = MDL.classify(value) if not unknown_logiciel else None
            logiciels_dict.subscribe(software)

        i += 1

    doc.add_paragraph(f"Total variables (avant traitement) : `{str(sum(1 for _ in dicts))}`, dont :")
    doc.add_unordered_list(
        [
            f"`{sum(1 for d in dicts if isinstance(d, StoreSet) and not d.removable())}` variables de type numérique",
            f"`{sum(1 for d in dicts if isinstance(d, StoreCollection) and not d.removable())}` variables de type catégorielle",
        ]
    )

    removable_dicts = []
    for dict in dicts:
        if dict.removable():
            removable_dicts.append(dict.name["default"])
    doc.add_paragraph(f"Variables supprimées par identification des données manquantes :")
    doc.add_unordered_list(removable_dicts)

    doc.add_heading("Vue d'ensemble des variables", level=2)
    doc.add_table(
        ["Nom", "Type", "Largeur", "Libellé", "Vérifiée"],
        [
            [
                f"🗑️ {dict.name['format']}" if dict.removable() else dict.name["format"],
                "Numérique" if isinstance(dict, StoreSet) else "Catégorielle",
                str(dict.length()),
                dict.name["default"],
                "✅" if dict.verified else "❌",
            ]
            for _, dict in enumerate(dicts)
        ],
    )

    for dict in dicts:
        if not dict.removable():
            dict.generate_rapport(dict)

    for dict in dicts:
        if not dict.removable():
            dict.handle_missing_data(dict)

    data.add_heading("Identification des données manquantes", level=3)
    rows = [["N", "VALIDE"], *[["", name] for name in UnwantedDataType.get()]]
    headers = [d.name["format"] for d in dicts if not d.removable()]
    for dict in dicts:
        if not dict.removable():
            rows[0].append(str(dict.length()))
            for i, type in enumerate(UnwantedDataType.get()):
                subset = [v for v in dict.invalid_subsets if v["type"] == UnwantedDataType[type]]
                rows[i + 1].append(str(len(subset)) if len(subset) != 0 else "")
    data.add_table(["", "", *headers], rows)

    stats.add_heading("Statistiques descriptives", level=2)
    for dict in dicts:
        if not dict.removable():
            dict.generate_statistics(dict)

    stats.add_heading("Analyse inférentielle", level=2)
    for dict in dicts:
        if not dict.removable():
            dict.analyze(dict)

    parser = argparse.ArgumentParser()
    parser.add_argument("--write", type=str, help="Spécifier sur quel fichier écrire")
    args = parser.parse_args()

    for arg in args.write.split(","):
        match arg:
            case "DOCS":
                doc.dump(arg, directory=MD_DIR)
            case "DATA":
                data.dump(arg, directory=MD_DIR)
            case "STATS":
                stats.dump(arg, directory=MD_DIR)
            case "NONE":
                pass
            case _:
                doc.dump("DOCS", directory=MD_DIR)
                data.dump("DATA", directory=MD_DIR)
                stats.dump("STATS", directory=MD_DIR)
