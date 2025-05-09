# External libs
import numpy as np
import snakemd as mkdn
import scipy.stats as scipy
import matplotlib.pyplot as plt

# Standard libs
import re
import os
import csv
import math
import enum
import shutil
import typing
import shutil
import zipfile
import tarfile
import argparse
import platform
import collections
from datetime import datetime
from unicodedata import normalize as normalize_unicode


OS_TYPE = platform.system().lower()

parser = argparse.ArgumentParser()
parser.add_argument("--write", type=str, help="Spécifier sur quel fichier écrire")
parser.add_argument(
    "--skip-geolocation",
    action="store_true",
    help="Ne pas générer de carte choroplèthe",
)
parser.add_argument(
    "--skip-visualization",
    action="store_true",
    help="Ne pas générer les représentations graphiques",
)
args = parser.parse_args()

doc = mkdn.Document()
data = mkdn.Document()
stats = mkdn.Document()

MD_DIR = "markdown"
ASSETS_DIR_NAME = "assets"
RESOURCES_DIR_NAME = "resources"

time_generated = datetime.now().strftime("%d/%m/%Y à %H:%M")
for markdown in [doc, data, stats]:
    markdown.add_heading(f"Analyse des données - Généré le {time_generated}")

def normalize(value: str) -> str:
    return (
        normalize_unicode("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
    )


# Référence: https://fr.wikipedia.org/wiki/Distance_de_Levenshtein
def levenshtein_distance(v1: str, v2: str):
    rows, cols = len(v1) + 1, len(v2) + 1
    dist = [[0 for _ in range(cols)] for _ in range(rows)]

    for i in range(1, rows):
        dist[i][0] = i
    for j in range(1, cols):
        dist[0][j] = j

    for i in range(1, rows):
        for j in range(1, cols):
            if v1[i - 1] == v2[j - 1]:
                cost = 0
            else:
                cost = 1
            dist[i][j] = min(
                dist[i - 1][j] + 1,
                dist[i][j - 1] + 1,
                dist[i - 1][j - 1] + cost,
            )

    return dist[-1][-1]


def matches_approx(s1: str, s2: str, threshold=2):
    distance = levenshtein_distance(s1, s2)
    return distance <= threshold

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
            if matches_approx(software, logiciel):
                return cls[software].name
        return cls.AUTRE.name


class Nullable:
    @classmethod
    def classify(cls, value: str) -> str | int:
        if "PAS" in value or "AUCUN" in value or "NON" in value or "RIEN" in value:
            return 0
        else:
            return value


class FileSystemManager:
    def __init__(self):
        for folder in [MD_DIR, ASSETS_DIR_NAME]:
            os.makedirs(folder, exist_ok=True)

    def flush(self):
        if not args.skip_visualization:
            for item in os.listdir(ASSETS_DIR_NAME):
                item_path = os.path.join(ASSETS_DIR_NAME, item)
                shutil.rmtree(item_path) if os.path.isdir(item_path) else os.unlink(item_path)

        for filename in os.listdir():
            if filename.endswith(".zip") or filename.endswith(".tar.gz"):
                os.remove(os.path.join(os.getcwd(), filename))

    def compress(self, file_ext: str):
        filename = datetime.now().strftime("%Y_%m_%d")
        folders_to_compress = [MD_DIR, ASSETS_DIR_NAME]

        if OS_TYPE == 'windows':
            archive_name = f"{filename}.{file_ext}"
            with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for folder in folders_to_compress:
                    if os.path.exists(folder):
                        for root, dirs, files in os.walk(folder):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, os.path.dirname(folder))
                                zipf.write(file_path, arcname)
        else:
            archive_name = f"{filename}.{file_ext}"
            with tarfile.open(archive_name, "w:gz") as tar:
                for folder in folders_to_compress:
                    if os.path.exists(folder):
                        tar.add(folder, arcname=os.path.basename(folder))

    def write(self):
        for arg in args.write.split(","):
            match arg:
                case "DOCS":
                    doc.dump(arg, directory=MD_DIR)
                case "DATA":
                    data.dump(arg, directory=MD_DIR)
                case "STATS":
                    stats.dump(arg, directory=MD_DIR)
                case _:
                    pass
        else:
            doc.dump("DOCS", directory=MD_DIR)
            data.dump("DATA", directory=MD_DIR)
            stats.dump("STATS", directory=MD_DIR)

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
        unique_outliers = np.unique(outliers)
        return list(map(int, unique_outliers))

    def handle_outliers(self, values: list[int]):
        filename = f"{ASSETS_DIR_NAME}/boxplot_{store.name['format']}.png"

        bp = plt.boxplot(values)
        median = bp["medians"][0].get_ydata()[0]

        plt.figure(figsize=(10, 6))
        plt.boxplot(values, vert=True, patch_artist=True)
        plt.title(f"Boxplot : {self.name['default']}", fontsize=14)
        plt.ylabel("Valeurs", fontsize=12)
        plt.grid(axis="y", alpha=0.75)
        plt.legend(
            [bp["medians"][0], bp["boxes"][0]],
            [f"Médiane : {median}", "IQR"],
        )

        plt.savefig(filename, dpi=120, bbox_inches="tight")

        data.add_heading(f"{self.name['default']} [{self.name['format']}]", level=4)
        data.add_block(mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")]))

    def impute_data(self, dict):
        if isinstance(dict, StoreSet):
            X = [x for x in dict.data if x is not None]

            outliers = dict.outliers(X)
            has_outliers = len(outliers) > 0

            for outlier in outliers:
                self.invalid_subsets.append({
                    "pos": dict.data.index(outlier),
                    "type": UnwantedDataType.OUTLIER,
                })

            if has_outliers:
                self.handle_outliers(X)

            def fallback_imputation(pos):
                imputed_value = np.median(X) if has_outliers else round(np.mean(X))
                dict.data[pos] = imputed_value

            for subset in dict.invalid_subsets:
                subset_pos = subset["pos"]
                best_corr = 0
                best_predictor_data = None

                for d in dicts:
                    if isinstance(d, StoreSet):
                        d_data_filtered = [val for val in d.data if val is not None][
                            : len(X)
                        ]

                        if len(d_data_filtered) == len(X):
                            corr, p_value = scipy.pearsonr(X, d_data_filtered)
                            if (
                                p_value < 0.05
                                and abs(corr) > 0.3
                                and abs(corr) > best_corr
                            ):
                                best_corr = abs(corr)
                                best_predictor_data = d_data_filtered

                try:
                    X_train = np.array(
                        best_predictor_data
                    )  # Independent variable (predictor)
                    y_train = np.array(X)  # Dependent variable (target)

                    slope, intercept, _, p_value, _ = scipy.linregress(X_train, y_train)
                    predictor_value = best_predictor_data[subset_pos]
                    value = round(intercept + slope * predictor_value)

                    # y = ax + b
                    dict.data[subset_pos] = value
                except (IndexError, ValueError, TypeError):
                    fallback_imputation(subset_pos)

        # Mode (VF)
        elif isinstance(dict, StoreCollection):
            for k, v in list(dict.data.items()):
                if v is None:
                    valid_data = [v for v in dict.data.values() if v is not None]
                    common_value = max(valid_data, key=lambda x: x["count"])
                    common_value["count"] += 1
                    dict.data.pop(k)
                    self.invalid_subsets = [
                        subset for subset in self.invalid_subsets if subset["pos"] != k
                    ]

    def generate_rapport(self, dict):
        data.add_heading(f"{dict.name['default']} [{dict.name['format']}]", level=4)
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

        row = collections.deque(
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

        for value in stores:
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

        if dict.invalid_subsets:
            data.add_block(
                mkdn.Quote(
                    f"Les valeurs non valides sont les suivantes : {', '.join(f'`{subset["value"]}`' for subset in dict.invalid_subsets)}"
                )
            )

    def generate_statistics(self, dict):
        if isinstance(dict, StoreSet):
            stats.add_heading(
                f"{dict.name['default']} [{dict.name['format']}]", level=3
            )
            stats.add_heading("Dispersion des données", level=4)

            headers = ["", "N", "Minimum", "Maximum", "Moyenne", "Écart type"]

            if any(x is None for x in dict.data):
                message = f"None values still exist in {dict.name["format"]} after handling missing data"
                raise ValueError(message, dict.data)

            min = np.min(dict.data)
            max = np.max(dict.data)
            mean = np.mean(dict.data)
            std = np.std(dict.data, ddof=1)
            cv = (std / mean) * 100

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

            if cv > 20:
                message = "L'écart-type est relativement élevé, ce qui veut dire qu'il y a une grande dispersion des données"
            else:
                message = "L'écart-type est relativement faible, ce qui veut dire que les valeurs sont proches de la moyenne"

            stats.add_block(mkdn.Quote(message))

            stats.add_heading("Distribution des données et test de normalité", level=4)
            headers = ["Kolmogrov-Smirnov", "Shapiro-Wilk"]
            sub_header = ["Statistiques", "ddl", "Sig."]
            header_styles = "style='text-align: center;' colspan='3'"

            shapiro_dn, shapiro_pvalue = scipy.shapiro(dict.data)
            kolmogrov_dn, kolmogorov_pvalue = scipy.kstest(
                dict.data, "norm", args=(mean, std)
            )

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
                filename = f"{ASSETS_DIR_NAME}/hist_{dict.name['format']}.png"

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
                plt.hist(
                    dict.data,
                    bins=10,
                    density=True,
                    alpha=0.7,
                    color="blue",
                    edgecolor="black",
                )

                x = np.linspace(min, max, 100)
                p = scipy.norm.pdf(x, mean, std)

                plt.xticks(
                    x_ticks,
                    labels=[
                        r"$\mu - 3\sigma$",
                        r"$\mu - 2\sigma$",
                        r"$\mu - \sigma$",
                        r"$\mu$",
                        r"$\mu + \sigma$",
                        r"$\mu + 2\sigma$",
                        r"$\mu + 3\sigma$",
                    ],
                )

                plt.plot(x, p, "r-", linewidth=2)
                plt.axvline(float(np.mean(dict.data)), ls="--", color="lightgray")
                plt.title("Histogramme avec une courbe de distribution normale")
                plt.xlabel(dict.name["default"])
                plt.ylabel("Probabilité de densité")
                plt.savefig(filename, dpi=120, bbox_inches="tight")

                stats.add_block(mkdn.Quote(message))
                stats.add_block(
                    mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")])
                )
            else:
                stats.add_block(mkdn.Quote(message))
                message = "Une distribution non normale"

    def visualize(self, store):
        # Génération d'une carte choroplèthe
        if store.name["format"] == "VD" and not args.skip_geolocation:
            import plotly.express as px
            import plotly.graph_objects as go
            import time

            AFRICAN_COUNTRIES = [
                "AO",
                "BJ",
                "BW",
                "BF",
                "BI",
                "CM",
                "CV",
                "CF",
                "TD",
                "KM",
                "CG",
                "CD",
                "DJ",
                "EG",
                "GQ",
                "ER",
                "SZ",
                "ET",
                "GA",
                "GM",
                "GH",
                "GN",
                "GW",
                "CI",
                "KE",
                "LS",
                "LR",
                "LY",
                "MG",
                "MW",
                "ML",
                "MR",
                "MU",
                "MA",
                "MZ",
                "NA",
                "NE",
                "NG",
                "RW",
                "ST",
                "SN",
                "SC",
                "SL",
                "SO",
                "ZA",
                "SS",
                "SD",
                "TZ",
                "TG",
                "TN",
                "UG",
                "ZM",
                "ZW",
            ]

            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

            def get_location_data(city_name: str, retries: int = 10, delay: int = 10):
                geolocator = Nominatim(user_agent="geoapi")
                for attempt in range(retries):
                    try:
                        if location := geolocator.geocode(
                            city_name, country_codes=AFRICAN_COUNTRIES, namedetails=True
                        ):
                            query = location.address.split(",")[0].strip()
                            residence = re.sub(r"[^a-zA-ZÀ-ÿ\s'-]", "", query).strip()
                            return location.latitude, location.longitude, residence
                    except (GeocoderTimedOut, GeocoderUnavailable) as e:
                        if attempt < retries - 1:
                            time.sleep(delay)
                        else:
                            print(
                                f"Erreur de géolocalisation en raison de : {e}. City: {city_name}. Trop de tentatives."
                            )
                return None, None, None

            city_lats, city_lons, areas, intensities = [], [], [], []

            for city in store.data.values():
                lat, lon, area = get_location_data(city["name"])
                if lat and lon and area:
                    city_lats.append(lat)
                    city_lons.append(lon)
                    areas.append(area)
                    intensities.append(city["count"])

            fig = px.choropleth(
                locations=list(set(areas)),
                locationmode="ISO-3",
                color=[areas.count(area) for area in set(areas)],
                scope="africa",
            )

            fig.add_trace(
                go.Scattergeo(
                    name="Cities",
                    mode="markers+text",
                    textposition="top center",
                    lon=city_lons,
                    lat=city_lats,
                    text=[
                        f"{city} ({count}) {'👥' if count > 1 else '👤'}"
                        for city, count in zip(areas, intensities)
                    ],
                    marker=dict(
                        size=[i * 6 for i in intensities],
                        color=intensities,
                        colorscale="YlOrRd",
                        colorbar=dict(title="City Intensity"),
                        cmin=min(intensities),
                        cmax=max(intensities),
                        showscale=True,
                        opacity=0.8,
                        line=dict(width=0.5, color="black"),
                    ),
                )
            )

            fig.update_layout(
                margin=dict(l=0, r=0, t=0, b=0),
                title_text="Carte choroplèthe de la VAR > Ville d'origine",
                showlegend=True,
                geo=dict(
                    resolution=110,
                    showsubunits=True,
                    subunitcolor="Blue",
                    showframe=False,
                    showcoastlines=False,
                    showland=True,
                    landcolor="whitesmoke",
                    showocean=True,
                    oceancolor="lightblue",
                    showcountries=True,
                    countrycolor="gray",
                ),
            )

            filename = f"./{ASSETS_DIR_NAME}/choropleth_{store.name['format']}"

            fig.write_image(
                f"{filename}.png", scale=3, height=2600, width=2200
            )  # Image simple
            fig.write_html(f"{filename}.html")  # Page interactive

        elif store.name["format"] in [
            "UD",
            "MDL",
            "TDLPU",
            "FDDRSPJ",
            "NDPSYNPS",
            "MB",
            "TPSLEPJ",
            "MDVU",
            "SPDR",
            "TDL",
            "PDMLDE",
            "NDLLPA",
            "TEPDE",
            "FD",
            "PADPA",
            "MS1",
            "MS2",
            "MS3",
            "MS4",
            "MS5",
        ]:
            fig = plt.figure(figsize=(10, 7))

            labels = [item["name"] for item in store.data.values()]
            data = [item["count"] for item in store.data.values()]

            max_index = data.index(max(data))
            explode = [0] * len(data)
            explode[max_index] = 0.1

            wedges, _, autotexts = plt.pie(
                data, labels=labels, explode=explode, autopct="%1.1f%%"
            )

            fig.legend(wedges, labels, loc="upper right")
            plt.setp(autotexts, size=12, weight="bold")
            plt.title(store.name["default"])
            plt.savefig(
                f"{ASSETS_DIR_NAME}/pie_{store.name['format']}.png",
                dpi=120,
                bbox_inches="tight",
            )

        elif store.name["format"] == "QDS":
            from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
            from matplotlib.offsetbox import OffsetImage, AnnotationBbox
            from io import BytesIO

            import cairosvg

            def load_svg(svg_path, size=(30, 30)):
                png_data = cairosvg.svg2png(
                    url=svg_path, output_width=size[0], output_height=size[1]
                )
                return plt.imread(BytesIO(png_data))

            categories = {
                "BAD": (1, 2),
                "POOR": (3, 4),
                "AVERAGE": (5, 6),
                "GOOD": (7, 8),
                "HAPPY": (9, 10),
            }

            scores = list(range(1, 11))
            frequencies = [
                collections.Counter(store.data).get(score, 0) for score in scores
            ]
            total_responses = sum(frequencies)
            percentages = [freq / total_responses * 100 for freq in frequencies]
            max_freq = max(frequencies)

            category_colors = ["#ff0000", "#ff6600", "#ffcc00", "#66cc00", "#009900"]
            cmap = LinearSegmentedColormap.from_list(
                "sleep_quality", category_colors, N=len(categories)
            )

            bounds = [1, 3, 5, 7, 9, 11]
            norm = BoundaryNorm(bounds, len(categories))

            # Plot setup
            fig, ax = plt.subplots(figsize=(12, 6))

            # Add percentage labels
            for score, freq, percent in zip(scores, frequencies, percentages):
                ax.text(score, freq + 0.5, f"{percent:.1f}%", ha="center", va="bottom")

            # Add category icons
            y_pos = max_freq * 1.1
            for category, (start, end) in categories.items():
                center = (start + end) / 2
                src = load_svg(f"./resources/{category}.svg")
                imagebox = OffsetImage(src, zoom=1.0)
                ax.add_artist(AnnotationBbox(imagebox, (center, y_pos), frameon=False))

            # Axes and titles
            ax.set_title(
                f"Distribution: {store.name['default']} (Scale 1-10)",
                fontsize=14,
                pad=20,
            )
            ax.set_xlabel("Sleep Quality Score", fontsize=12)
            ax.set_ylabel("Frequency", fontsize=12)
            ax.set_xticks(scores)
            ax.set_ylim(0, max_freq * 1.25)

            # Color bar (legend)
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(
                sm, ax=ax, orientation="horizontal", pad=0.05, ticks=[2, 4, 6, 8, 10]
            )
            cbar.set_label("Sleep Quality Categories")
            cbar.ax.set_xticklabels(["BAD", "POOR", "AVERAGE", "GOOD", "HAPPY"])

            plt.savefig(
                f"{ASSETS_DIR_NAME}/scale_{store.name['format']}.png",
                dpi=120,
                bbox_inches="tight",
            )


class StoreCollection(DataManager):
    def __init__(
        self,
        pos,
        method: typing.Literal["exact", "approx"] = "exact",
        recursive=False,
        nullish=False,
    ):
        self.pos = pos
        self.data = {}
        self.method = method
        self.raw = []
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.recursive = recursive
        self.nullish = nullish

    def cleanup(self, value):
        if value:
            if self.nullish:
                return str(Nullable.classify(value.upper()))
            else:
                return normalize(value).upper()
        else:
            return 0

    def in_depth(self, value: str):
        parts = re.split(r"[;,/-]| ET ", value)
        matches = []

        for v in parts:
            matches.append(v.strip())

        return matches

    def subscribe(self, value: str | None):
        value = self.cleanup(value)

        if value == "0":
            value = "AUCUN"

        def unresolved(type, v):
            self.data[len(self.data)] = None
            self.invalid_subsets.append(
                {"pos": len(self.data) - 1, "type": type, "value": v}
            )

        def resolve(key):
            self.raw.append(key)
            self.data[key]["count"] += 1

        if not value or self.is_unknown(value):
            return unresolved(UnwantedDataType.MISSING, value)
        elif (
            value
            and not re.search(r"[a-zA-Z]", value.strip())
            and not re.fullmatch(r"\d+(?:\s*-\s*\d+)?", value.strip())
        ):
            return unresolved(UnwantedDataType.INVALID_FORMAT, value)

        if self.recursive and len(possible_values := self.in_depth(value)) > 1:
            for p_value in possible_values:
                self.subscribe(p_value)
            return

        for key, info in self.data.items():
            if info is None:
                continue
            if self.method == "approx" and matches_approx(value, info["name"]):
                return resolve(key)
            elif self.method == "exact" and info["name"] == value:
                return resolve(key)
            elif self.method != "exact" and (
                info["name"] in value or value in info["name"]
            ):
                return resolve(key)
        self.data[len(self.data)] = {"name": value, "count": 1}
        self.raw.append(0)

    def length(self) -> int:
        return sum(item["count"] for item in self.data.values() if item is not None)


class StoreSet(DataManager):
    def __init__(self, pos, nullish=False):
        self.pos = pos
        self.data = []
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.nullish = nullish

    def cleanup(self, value):
        if isinstance(value, str):
            if self.nullish:
                return Nullable.classify(value.upper())
            else:
                return value.strip()
        else:
            return value

    def collect(self, value: int | str | None):
        value = self.cleanup(value)

        def unresolved(type, v):
            self.data.append(None)
            self.invalid_subsets.append(
                {"pos": len(self.data) - 1, "type": type, "value": v}
            )

        if self.is_unknown(value):
            return unresolved(UnwantedDataType.MISSING, value)

        if isinstance(value, int):
            return self.data.append(value)
        elif isinstance(value, str):
            if match := re.search(r"(\d+)", value):
                value = int(match.group(1))
                return self.data.append(value)
            else:
                unresolved(UnwantedDataType.INVALID_FORMAT, value)

    def length(self) -> int:
        return len([item for item in self.data if item is not None])


class Khi2Test:
    def __init__(self, dep_var: StoreCollection, indep_var: StoreCollection):
        self.dep_var = dep_var
        self.indep_var = indep_var
        self.table_rows = []

    def gen_contingency_table(self):
        stats.add_heading(
            f"{self.dep_var.name['default']} [{self.dep_var.name['format']}] -> {self.indep_var.name['default']} [{self.indep_var.name['format']}]",
            level=3,
        )
        stats.add_heading("Tableau de contingence (croisé)", level=4)

        indep_var_labels = [v["name"] for v in self.indep_var.data.values()]

        cumul_indep_var_values = [0 for _ in indep_var_labels]
        cumul_dep_var_values = 0
        min_len = min(len(self.dep_var.raw), len(self.indep_var.raw))

        for key, value in self.dep_var.data.items():
            row = [value["name"]]
            count_dep_var = 0

            for i, (field_key, _) in enumerate(self.indep_var.data.items()):
                count = sum(
                    1
                    for k in range(min_len)
                    if self.dep_var.raw[k] == key and self.indep_var.raw[k] == field_key
                )

                row.append(str(count))
                count_dep_var += count
                cumul_indep_var_values[i] += count

            row.append(str(count_dep_var))
            cumul_dep_var_values += count_dep_var
            self.table_rows.append(row)

        self.table_rows.append(
            ["TOTAL", *map(str, cumul_indep_var_values), str(cumul_dep_var_values)]
        )
        stats.add_table(["Éléments", *indep_var_labels, "TOTAL"], self.table_rows)

    def gen_khi_square_table(self):
        stats.add_heading("Tableau du Khi-Carré (χ²)", level=4)

        headers = ["", "Valeur", "dll", "Sig."]

        observed_data = []
        for row in self.table_rows[:-1]:
            observed_data.append([int(x) for x in row[1:-1]])

        observed = np.array(observed_data)
        non_zero_row_mask = np.any(observed != 0, axis=1)
        non_zero_col_mask = np.any(observed != 0, axis=0)
        filtered_observed = observed[non_zero_row_mask][:, non_zero_col_mask]

        chi2, p_value, dof, expected = scipy.chi2_contingency(
            filtered_observed, lambda_="log-likelihood"
        )  # fonction de vraisemblance

        rows = [
            ["Khi-Carré de Pearson", f"{chi2:.3f}", dof, f"{p_value:.3f}"],
            ["Rapport de vraisemblance", "", dof, ""],
            ["N d'observations valides", np.sum(observed), "", ""],
        ]

        stats.add_table(headers, rows)

        interpretation = (
            f"Le test du Khi-deux de Pearson indique une association "
            f"__{'statistiquement significative' if p_value < 0.05 else 'non significative'}__ "
            f"entre {self.dep_var.name['default'].lower()} et {self.indep_var.name['default'].lower()}"
        )

        percent_under_5 = (np.sum(expected < 5) / observed.size) * 100

        if percent_under_5 > 20 or np.min(expected) < 1:
            interpretation += (
                "Attention : Les conditions d'application du test ne sont pas pleinement respectées "
                "(plus de 20% des effectifs théoriques < 5 ou effectif minimum < 1). "
                "Les résultats doivent être interprétés avec prudence."
            )

        stats.add_paragraph(interpretation)


# Importation des données
with open(file="data.csv", mode="r", encoding="utf-8") as file:
    file = csv.reader(file)
    headers, doc_headers = next(file), []

    fs_manager = FileSystemManager()

    # Création des variables
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

        if formatted_header in headers:
            formatted_header = (
                f"{formatted_header}_{headers.count(formatted_header) + 1}"
            )

        doc_headers.append({"format": formatted_header, "default": header})
        headers[i] = formatted_header

    useless_dicts = ["ND", "AD", "HORODATEUR"]
    unreliable_dicts = ["MDL", "MS5"]
    removed_headers = [
        header["default"] for header in doc_headers if header["format"] in useless_dicts
    ]

    # Suppression des données sensibles et/ou inutiles
    for i in useless_dicts:
        index = headers.index(i)
        headers.pop(index)
        doc_headers.pop(index)
        file = [row[:index] + row[index + 1:] for row in file]

    # Traitement des données numériques et alphanumériques (catégorielles)
    ages_set = StoreSet(headers.index("AGE"))
    city_dict = StoreCollection(headers.index("VD"), method="approx")
    mentions_dicts = [StoreCollection(headers.index(f"MS{i}")) for i in range(1, 6)]
    mentionbac_dict = StoreCollection(headers.index("MB"))
    padpa_dict = StoreCollection(headers.index("PADPA"))
    sex_dict = StoreCollection(headers.index("GENRE"))
    anneebac_set = StoreSet(headers.index("ADDB"))
    ndfelsca_dict = StoreSet(headers.index("NDFELSCA"))
    studyfield_dict = StoreCollection(headers.index("FD"), method="approx")
    optionbac_dict = StoreCollection(headers.index("OB"))
    excel_dict = StoreCollection(headers.index("UD"))
    logiciels_dict = StoreCollection(headers.index("MDL"), recursive=True)
    nddps_dict = StoreSet(headers.index("NDDPS"))
    tdl_dict = StoreCollection(headers.index("TDL"), method="approx")
    mp_dict = StoreCollection(headers.index("MP"), method="approx", recursive=True)
    tpslepj_dict = StoreCollection(headers.index("TPSLEPJ"))
    mdvu_dict = StoreCollection(
        headers.index("MDVU"), method="approx", recursive=True, nullish=True
    )
    cdfvvpa_dict = StoreSet(headers.index("CDFVVPA"), nullish=True)
    caepm_dict = StoreSet(headers.index("CAEPM"), nullish=True)
    nddtps_dict = StoreSet(headers.index("NDDTPS"), nullish=True)
    tepde_dict = StoreCollection(headers.index("TEPDE"))
    spdr_dict = StoreCollection(headers.index("SPDR"), recursive=True)
    qds_dict = StoreSet(headers.index("QDS"))
    dmm_dict = StoreSet(headers.index("DMM"), nullish=True)
    lp_dict = StoreCollection(headers.index("LP"), recursive=True)
    ndllpa_dict = StoreCollection(headers.index("NDLLPA"))
    tdsp_dict = StoreCollection(
        headers.index("TDSP"), method="approx", recursive=True, nullish=True
    )
    ap_dict = StoreSet(headers.index("AP"))
    nmddspn_dict = StoreSet(headers.index("NMDDSPN"))
    ndpsynps_dict = StoreCollection(headers.index("NDPSYNPS"))
    pdmlde_dict = StoreCollection(headers.index("PDMLDE"))
    tdlpu_dict = StoreCollection(headers.index("TDLPU"), recursive=True)
    fddrspj_dict = StoreCollection(headers.index("FDDRSPJ"))

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
        for store in dicts:
            if store not in [anneebac_set, optionbac_dict, logiciels_dict]:
                if isinstance(store, StoreCollection):
                    store.subscribe(rows[i][store.pos])
                elif isinstance(store, StoreSet):
                    store.collect(rows[i][store.pos])

        match = re.search(r"(\d{4})[-/_\s]*(\d{4})?", rows[i][anneebac_set.pos])
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

    fs_manager.flush()

    doc.add_paragraph(
        f"Total variables traitées : `{str(sum(1 for dict in dicts if not dict.removable()))}`, dont :"
    )
    doc.add_unordered_list(
        [
            f"`{sum(1 for d in dicts if isinstance(d, StoreSet) and not d.removable())}` variables de type numérique",
            f"`{sum(1 for d in dicts if isinstance(d, StoreCollection) and not d.removable())}` variables de type catégorielle",
        ]
    )

    removable_dicts = []
    for store in dicts:
        if store.removable():
            removable_dicts.append(store.name["default"])
    doc.add_paragraph(
        "Variables supprimées par identification des données manquantes :"
    )
    doc.add_unordered_list(removable_dicts)

    doc.add_paragraph("Variables non-pertinentes dans notre analyse :")
    doc.add_unordered_list(removed_headers)

    doc.add_paragraph("Variables biaisées :")
    doc.add_unordered_list(
        [
            header["default"]
            for header in doc_headers
            if header["format"] in unreliable_dicts
        ]
    )

    doc.add_heading("Vue d'ensemble des variables", level=2)
    doc.add_table(
        ["Nom", "Type", "Largeur", "Libellé", "Méthode utilisée", "Récursive"],
        [
            [
                f"🗑️ {dict.name['format']}" if dict.removable() else dict.name["format"],
                "Numérique" if isinstance(dict, StoreSet) else "Catégorielle",
                str(dict.length()),
                dict.name["default"],
                dict.method if isinstance(dict, StoreCollection) else " ",
                "✅" if isinstance(dict, StoreCollection) and dict.recursive else "❌",
            ]
            for _, dict in enumerate(dicts)
        ],
    )

    for store in dicts:
        if not store.removable():
            store.generate_rapport(store)

    for store in dicts:
        if not store.removable():
            store.impute_data(store)

    data.add_heading("Identification des données manquantes", level=3)
    table_rows = [["N", "VALIDE"], *[["", name] for name in UnwantedDataType.get()]]
    headers = [d.name["format"] for d in dicts if not d.removable()]
    for store in dicts:
        if not store.removable():
            table_rows[0].append(str(store.length()))
            for i, type in enumerate(UnwantedDataType.get()):
                subset = [
                    v
                    for v in store.invalid_subsets
                    if v["type"] == UnwantedDataType[type]
                ]
                table_rows[i + 1].append(str(len(subset)) if len(subset) != 0 else "")
    data.add_table(["", "", *headers], table_rows)

    stats.add_heading("Statistiques descriptives", level=2)
    for store in dicts:
        if not store.removable():
            store.generate_statistics(store)

    # Hypothèse 1 : Genre -> filière
    hypothesis = Khi2Test(sex_dict, studyfield_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    # Hypothèse 2 : Option BAC -> Filière d'étude
    hypothesis = Khi2Test(optionbac_dict, studyfield_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    # Hypothèse 3 : Fréquence d'utilisation des réseaux sociaux par jour -> Temps passé sur les écrans par jour
    hypothesis = Khi2Test(fddrspj_dict, tpslepj_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    # Hypothèse 4 : Source principale de revenu -> Type de logement
    hypothesis = Khi2Test(tdl_dict, spdr_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    # Hypothèse 5 : Type d'application la plus utilisée -> Temps passé sur les écrans par jour
    hypothesis = Khi2Test(tdlpu_dict, tpslepj_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    stats.add_heading("Analyse inférentielle", level=2)

    # Hypothèse 6 : Test t pour un échantillon (Si la moyenne de CAEPM est différente ou pas d'une valeur théorique)
    theorical_value = 300
    t_stat, p_value = scipy.ttest_1samp(caepm_dict.data, theorical_value)

    stats.add_heading(
        f"Est-ce que la capacité moyenne à économiser par mois est différente de {theorical_value} DH (Valeur théorique) ?",
        level=3,
    )
    stats.add_unordered_list(
        [
            "H0 : Moyenne observée = valeur théorique (u = u0)",
            "H1 : Moyenne observée ≠ Valeur théorique (u != u0)",
        ]
    )
    stats.add_heading("Statistiques sur échantillon uniques", level=4)

    mean = np.mean(caepm_dict.data)
    std = np.std(caepm_dict.data, ddof=1)
    n_length = caepm_dict.length()
    std_error = std / math.sqrt(n_length)

    headers = ["", "N", "Moyenne", "Écart-type", "Moyenne erreur standard"]
    row = [
        caepm_dict.name["format"],
        n_length,
        f"{mean:.3f}",
        f"{std:.3f}",
        f"{std_error:.3f}",
    ]
    stats.add_table(headers, [row])

    stats.add_heading(f"Test sur échantillon unique ({theorical_value})", level=4)

    mean_diff = mean - theorical_value
    confidence_level = 0.95
    t_critical = scipy.t.ppf(
        1 - (1 - confidence_level) / 2, n_length - 1
    )  # ddof (sample) = n - 1
    margin_error = t_critical * std_error
    lower_bound = mean_diff - margin_error
    upper_bound = mean_diff + margin_error

    headers = [
        "",
        "t",
        "dll",
        "Sig. (bilatéral)",
        "Différence moyenne",
        "IDCD Inférieur",
        "IDCD Supérieur",
    ]
    row = [
        caepm_dict.name["format"],
        f"{t_stat:.3f}",
        n_length,
        f"{p_value:.3f}",
        f"{mean_diff:.3f}",
        f"{lower_bound:.3f}",
        f"{upper_bound:.3f}",
    ]
    stats.add_table(headers, [row])

    stats.add_paragraph(
        f"(*) IDCD : Intervalle de confiance de la différence à {confidence_level * 100}%"
    )

    interpretation = (
        f"{'La moyenne __diffère significativement__ de' if p_value < 0.05 else '__Aucune différence significative__ avec'} "
        f"la valeur théorique (p {'<' if p_value < 0.05 else '>='} 0.05)"
    )

    stats.add_paragraph(interpretation)

    # Hypothèse 7 : Test t pour échantillon indépendant (Si la moyenne de DMM est différente entre deux groupes sur la base du GENRE)

    stats.add_heading(
        "Y a-t'il une différence entre les dépenses mensuelles moyennes des garçons et filles ?",
        level=3,
    )
    stats.add_unordered_list(
        [
            "H0 : Aucune différence/relation entre les deux groupes",
            "H1 : Une différence/relation existe entre les deux groupes",
        ]
    )

    stats.add_heading("Statistiques de groupe", level=4)

    headers = [
        "",
        sex_dict.name["format"],
        "N",
        "Moyenne",
        "Écart-type",
        "Moyenne erreur standard",
    ]
    rows = []

    for k, value in sex_dict.data.items():
        group_data = [val for val, sex in zip(dmm_dict.data, sex_dict.raw) if sex == k]

        n = len(group_data)
        mean = np.mean(group_data)
        std = np.std(group_data, ddof=1)
        std_error = std / math.sqrt(n)

        rows.append(
            [
                "" if k != 0 else dmm_dict.name["format"],
                value["name"],
                n,
                f"{mean:.3f}",
                f"{std:.3f}",
                f"{std_error:.3f}",
            ]
        )

    stats.add_table(headers, rows)

    stats.add_heading("Test des échantillons indépendants", level=4)

    group1 = [val for val, sex in zip(dmm_dict.data, sex_dict.raw) if sex == 0]
    group2 = [val for val, sex in zip(dmm_dict.data, sex_dict.raw) if sex == 1]

    levene_stat, levene_p = scipy.levene(group1, group2)

    ttest_eq = scipy.ttest_ind(group1, group2, equal_var=True)
    ttest_uneq = scipy.ttest_ind(group1, group2, equal_var=False)

    mean_diff = np.mean(group1) - np.mean(group2)

    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    n1, n2 = len(group1), len(group2)

    pooled_var = ((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2)

    std_err_eq = np.sqrt(pooled_var * (1 / n1 + 1 / n2))
    std_err_uneq = np.sqrt(var1 / n1 + var2 / n2)

    ddl_eq = n1 + n2 - 2
    ddl_uneq = (var1 / n1 + var2 / n2) ** 2 / (
        (var1 / n1) ** 2 / (n1 - 1) + (var2 / n2) ** 2 / (n2 - 1)
    )

    t_critical_eq = scipy.t.ppf(0.975, ddl_eq)
    t_critical_uneq = scipy.t.ppf(0.975, ddl_uneq)

    margin_of_error_eq = t_critical_eq * std_err_eq
    margin_of_error_uneq = t_critical_uneq * std_err_uneq

    conf_int_eq = (mean_diff - margin_of_error_eq, mean_diff + margin_of_error_eq)
    conf_int_uneq = (mean_diff - margin_of_error_uneq, mean_diff + margin_of_error_uneq)

    headers = [
        "",
        "",
        "F",
        "Sig.",
        "t",
        "dll",
        "Sig. (bilatéral)",
        "Différence moyenne",
        "Différence erreur standard",
        "IDCD Inférieur",
        "IDCD Supérieur",
    ]
    rows = [
        [
            dmm_dict.name["format"],
            "Hypothèse de variances égales",
            f"{levene_stat:.3f}",
            f"{levene_p:.3f}",
            f"{ttest_eq.statistic:.3f}",
            f"{ddl_eq:.1f}",
            f"{ttest_eq.pvalue:.3f}",
            f"{mean_diff:.3f}",
            f"{std_err_eq:.3f}",
            f"{conf_int_eq[0]:.3f}",
            f"{conf_int_eq[1]:.3f}",
        ],
        [
            "",
            "Hypothèse de variances inégales",
            "",
            "",
            f"{ttest_uneq.statistic:.3f}",
            f"{ddl_uneq:.1f}",
            f"{ttest_uneq.pvalue:.3f}",
            f"{mean_diff:.3f}",
            f"{std_err_uneq:.3f}",
            f"{conf_int_uneq[0]:.3f}",
            f"{conf_int_uneq[1]:.3f}",
        ],
    ]

    stats.add_table(headers, rows)

    ttest = ttest_eq if levene_p < 0.05 else ttest_uneq

    interpretation = (
        f"Il {'existe une différence statistiquement' if ttest.pvalue < 0.05 else "n'y a pas de différence"} "
        "significative entre les dépenses mensuelles moyennes des garçons et filles"
    )

    stats.add_paragraph(interpretation)

    # Hypothèse 8 : ANOVA - Comparaison de plus de 2 groupes (2 moyennes)

    stats.add_heading(
        "Est-ce que le travail en parallèle des études influence le nombre d'heures d'étude par semaine ?",
        level=3,
    )
    stats.add_unordered_list(
        [
            "H0 : Aucune différence/relation entre les deux groupes",
            "H1 : Une différence/relation existe entre les deux groupes",
        ]
    )

    stats.add_heading("ANOVA à 1 facteur", level=4)

    group1 = [val for val, typ in zip(dmm_dict.data, tepde_dict.raw) if typ == 0]
    group2 = [val for val, typ in zip(dmm_dict.data, tepde_dict.raw) if typ == 1]

    f_value, p_value = scipy.f_oneway(group1, group2)

    mean_all = np.mean(group1 + group2)
    ss_total = np.sum((np.concatenate([group1, group2]) - mean_all) ** 2)
    ss_between = (
        len(group1) * (np.mean(group1) - mean_all) ** 2
        + (len(group2)) * (np.mean(group2) - mean_all) ** 2
    )
    ss_within = ss_total - ss_between

    df_between = 1
    df_within = len(group1) + len(group2) - 2
    df_total = len(group1) + len(group2) - 1

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within

    headers = ["", "Somme des carrés", "dll", "Carré moyen", "F", "Sig."]
    rows = [
        [
            "Intergroupes",
            f"{ss_between:.3f}",
            df_between,
            f"{ms_between:.3f}",
            f"{f_value:.3f}",
            f"{p_value:.3f}",
        ],
        ["Intragroupes", f"{ss_within:.3f}", df_within, f"{ms_within:.3f}", "", ""],
        ["Total", f"{ss_total:.3f}", df_total, "", "", ""],
    ]

    stats.add_table(headers, rows)

    stats.add_paragraph(
        f"Résultat ANOVA: F({df_between},{df_within}) = {f_value:.3f}, p = {p_value:.3f}"
    )

    if p_value < 0.05:
        mean1 = np.mean(group1)
        mean2 = np.mean(group2)
        stats.add_paragraph(
            "Conclusion: Nous rejetons H0 (p < 0.05). Il existe une différence significative entre les groupes."
        )
        stats.add_paragraph(
            f"Les étudiants qui ne travaillent pas étudient en moyenne {mean1:.1f} heures/semaine "
            f"contre {mean2:.1f} heures/semaine pour ceux qui travaillent."
        )
    else:
        stats.add_paragraph(
            "Conclusion: Nous ne pouvons pas rejeter H0 (p ≥ 0.05). Aucune différence significative n'a été détectée."
        )

    # Hypothèse 9 : Test du Chi-Deux (Association entre variables qualitatives)

    stats.add_heading(
        "Est-ce que le genre a une association avec la participation aux projets académiques/professionnels ?",
        level=3,
    )
    stats.add_unordered_list(
        [
            "H0 : Aucune association entre les deux variables",
            "H1 : Une association significative existe entre les deux variables catégorielles",
        ]
    )

    hypothesis = Khi2Test(sex_dict, padpa_dict)
    hypothesis.gen_contingency_table()
    hypothesis.gen_khi_square_table()

    for store in dicts:
        if not store.removable() and not args.skip_visualization:
            store.visualize(store)

    stores = np.array([store for store in dicts if isinstance(store, StoreSet) and not store.removable()])
    corr_matrix = np.corrcoef([store.data for store in stores])

    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(corr_matrix, cmap='coolwarm', vmin=-1, vmax=1)

    cbar = ax.figure.colorbar(im, ax=ax)
    cbar.ax.set_ylabel("Coefficient de corrélation", rotation=-90, va="bottom")

    ax.set_xticks(np.arange(len(stores)))
    ax.set_yticks(np.arange(len(stores)))
    names = [store.name["format"] for store in stores]
    ax.set_xticklabels(names)
    ax.set_yticklabels(names)

    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    for i in range(len(stores)):
        for j in range(len(stores)):
            text = ax.text(j, i, f"{corr_matrix[i, j]:.2f}",
                        ha="center", va="center", color="w")
    
    ax.set_title("Matrice de corrélation")
    fig.tight_layout()
    plt.savefig(f"{ASSETS_DIR_NAME}/matrice_correlation.png", dpi=120, bbox_inches="tight")

    if args.write:
        fs_manager.write()

file_ext = "zip" if OS_TYPE == "windows" else "tar.gz"
confirm = input(f"Voulez-vous compresser les résultats en un seul fichier ({file_ext}) ? (o/n) : ")

if confirm == "o":
    fs_manager.compress(file_ext)
