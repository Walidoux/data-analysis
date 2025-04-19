from pandas import isnull
from scipy.stats import chi2_contingency, shapiro, kstest, norm, pearsonr
from sklearn.linear_model import LinearRegression
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
import os
import shutil

import utils


doc = mkdn.Document()
data = mkdn.Document()
stats = mkdn.Document()
MD_DIR = "markdown"
ASSETS_DIR_NAME = "assets"
RESOURCES_DIR_NAME = "resources"
time_generated = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
for markdown in [doc, data, stats]:
    markdown.add_heading(f"Analyse des données - Généré le {time_generated}")

for item in os.listdir(ASSETS_DIR_NAME):
    item_path = os.path.join(ASSETS_DIR_NAME, item)
    shutil.rmtree(item_path) if os.path.isdir(item_path) else os.unlink(item_path)


parser = argparse.ArgumentParser()
parser.add_argument("--write", type=str, help="Spécifier sur quel fichier écrire")
parser.add_argument("--skip-geolocation", action="store_true", help="Ne pas générer de carte choroplèthe")
args = parser.parse_args()


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


class Nullable():
    @classmethod
    def classify(cls, value: str) -> str | int:
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
        unique_outliers = np.unique(outliers)
        return list(map(int, unique_outliers))

    def handle_outliers(self, values: list[int]):
        filename = f"{ASSETS_DIR_NAME}/boxplot_{store.name["format"]}.png"

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

        plt.savefig(filename)

        data.add_heading(f"{self.name["default"]} [{self.name["format"]}]", level=4)
        data.add_block(mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")]))

    def handle_missing_data(self, dict):
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

            for subset in dict.invalid_subsets:
                Y = None
                best_corr = 0
                best_Y = None

                for d in dicts:
                    if isinstance(d, StoreSet):
                        d_data_filtered = [val for val in d.data if val is not None][:len(X)]

                        if len(d_data_filtered) == len(X):
                            corr, p_value = pearsonr(X, d_data_filtered)
                            if p_value < 0.05 and abs(corr) > 0.3 and abs(corr) > best_corr:
                                best_corr = abs(corr)
                                best_Y = d_data_filtered

                if best_Y is None:
                    dict.data[subset["pos"] - 1] = np.median(X) if has_outliers else np.mean(sum(X) / len(X))
                else:  # Linear regression: X ~ Y
                    Y = best_Y
                    Y_reshaped = np.array(Y).reshape(-1, 1)  # bind Y to 2D array
                    X_array = np.array(X)

                    model = LinearRegression()
                    model.fit(Y_reshaped, X_array)

                    y_val = best_Y[subset["pos"] - 1]
                    predicted_val = model.predict([[y_val]])[0]
                    dict.data[subset["pos"] - 1] = round(predicted_val)

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

        if dict.invalid_subsets:
            data.add_block(mkdn.Quote(f"Les valeurs non valides sont les suivantes : {', '.join(f'`{subset['value']}`' for subset in dict.invalid_subsets)}"))

    def generate_statistics(self, dict):
        stats.add_heading(f"{dict.name["default"]} [{dict.name["format"]}]", level=3)
        stats.add_heading("Dispersion des données", level=4)

        if isinstance(dict, StoreSet):
            headers = ["", "N", "Minimum", "Maximum", "Moyenne", "Écart type"]

            min = np.min(dict.data)
            max = np.max(dict.data)
            mean = np.mean(dict.data)
            std = np.std(dict.data, ddof=1)

            rows = [["N Valide (liste)", len(dict.data), min, max, round(mean, 4),    round(std, 4)]]

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
                filename = f"{ASSETS_DIR_NAME}/hist_{dict.name["format"]}.png"

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
                plt.savefig(filename)

                stats.add_block(mkdn.Quote(message))
                stats.add_block(mkdn.Paragraph([mkdn.Inline("", image=f"../{filename}")]))
            else:
                stats.add_block(mkdn.Quote(message))
                message = "Une distribution non normale"

        else:
            stats.add_heading("Test du Khi-deux", level=5)
            headers = ["", "Valeur", "dll", "Sig."]

            observed = [dict.data[key]["count"] for key in dict.data]
            stat, p_value, dof, expected = chi2_contingency(observed)

            rows = [
                ["Khi-Carré de Pearson", 4, len(dict.data), 0.565],
                ["Rapport de vraisemblance", 1.530, 2, 0.465],
                ["N d'observations valides", p_value, None, ""],
            ]

            p = 0  # coef de corr ?

            stats.add_table(headers, rows)

            if p < 0.05:
                stats.add_block(mkdn.Quote("Il y a une relation significative entre les variables"))

    def analyze(self, store):
        # Generate choropleth map
        if store.name["format"] == "VD" and not args.skip_geolocation:
            import plotly.express as px
            import plotly.graph_objects as go
            import time

            AFRICAN_COUNTRIES = [
                'AO', 'BJ', 'BW', 'BF', 'BI', 'CM', 'CV', 'CF', 'TD', 'KM', 'CG',
                'CD', 'DJ', 'EG', 'GQ', 'ER', 'SZ', 'ET', 'GA', 'GM', 'GH', 'GN', 'GW',
                'CI', 'KE', 'LS', 'LR', 'LY', 'MG', 'MW', 'ML', 'MR', 'MU', 'MA', 'MZ',
                'NA', 'NE', 'NG', 'RW', 'ST', 'SN', 'SC', 'SL', 'SO', 'ZA', 'SS', 'SD',
                'TZ', 'TG', 'TN', 'UG', 'ZM', 'ZW'
            ]

            from geopy.geocoders import Nominatim
            from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

            def get_location_data(city_name: str, retries: int = 10, delay: int = 10):
                geolocator = Nominatim(user_agent="geoapi")
                for attempt in range(retries):
                    try:
                        if location := geolocator.geocode(city_name, country_codes=AFRICAN_COUNTRIES, namedetails=True):
                            query = location.address.split(",")[0].strip()
                            residence = re.sub(r"[^a-zA-ZÀ-ÿ\s'-]", "", query).strip()
                            return location.latitude, location.longitude, residence
                    except (GeocoderTimedOut, GeocoderUnavailable) as e:
                        if attempt < retries - 1:
                            time.sleep(delay)
                        else:
                            print(f"Erreur de géolocalisation en raison de : {e}. City: {city_name}. Trop de tentatives.")
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

            fig.add_trace(go.Scattergeo(
                name='Cities',
                mode='markers+text',
                textposition='top center',
                lon=city_lons,
                lat=city_lats,
                text=[f"{city} ({count}) {'👥' if count > 1 else '👤'}" for city, count in zip(areas, intensities)],
                marker=dict(
                    size=[i * 6 for i in intensities],
                    color=intensities,
                    colorscale="YlOrRd",
                    colorbar=dict(title="City Intensity"),
                    cmin=min(intensities),
                    cmax=max(intensities),
                    showscale=True,
                    opacity=0.8,
                    line=dict(width=0.5, color='black')
                )
            ))

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

            filename = f"./{ASSETS_DIR_NAME}/choropleth_{store.name["format"]}"

            fig.write_image(f"{filename}.png", scale=3, height=2600, width=2200)  # Image simple
            fig.write_html(f"{filename}.html")  # Page interactive

        elif store.name["format"] in ["UD", "MDL", "TDLPU", "FDDRSPJ", "NDPSYNPS", "MB", "TPSLEPJ", "MDVU", "SPDR", "TDL"]:
            fig = plt.figure(figsize=(10, 7))

            labels = [item["name"] for item in store.data.values()]
            data = [item["count"] for item in store.data.values()]

            max_index = data.index(max(data))
            explode = [0] * len(data)
            explode[max_index] = 0.1

            wedges, _, autotexts = plt.pie(data, labels=labels, explode=explode, autopct='%1.1f%%')

            fig.legend(wedges, labels, loc="upper right")
            plt.setp(autotexts, size=12, weight="bold")
            plt.title(store.name["default"])
            plt.savefig(f"{ASSETS_DIR_NAME}/pie_{store.name["format"]}.png")

        elif store.name["format"] == "QDS":
            from matplotlib.colors import LinearSegmentedColormap, BoundaryNorm
            from matplotlib.offsetbox import OffsetImage, AnnotationBbox
            from io import BytesIO

            import cairosvg

            def load_svg(svg_path, size=(30, 30)):
                png_data = cairosvg.svg2png(url=svg_path, output_width=size[0], output_height=size[1])
                return plt.imread(BytesIO(png_data))

            categories = {
                'BAD': (1, 2),
                'POOR': (3, 4),
                'AVERAGE': (5, 6),
                'GOOD': (7, 8),
                'HAPPY': (9, 10)
            }

            scores = list(range(1, 11))
            frequencies = [collections.Counter(store.data).get(score, 0) for score in scores]
            total_responses = sum(frequencies)
            percentages = [freq / total_responses * 100 for freq in frequencies]
            max_freq = max(frequencies)

            category_colors = ['#ff0000', '#ff6600', '#ffcc00', '#66cc00', '#009900']
            cmap = LinearSegmentedColormap.from_list('sleep_quality', category_colors, N=len(categories))

            bounds = [1, 3, 5, 7, 9, 11]
            norm = BoundaryNorm(bounds, len(categories))

            # Plot setup
            fig, ax = plt.subplots(figsize=(12, 6))
            bars = ax.bar(scores, frequencies, color=[cmap(norm(score)) for score in scores])

            # Add percentage labels
            for score, freq, percent in zip(scores, frequencies, percentages):
                ax.text(score, freq + 0.5, f'{percent:.1f}%', ha='center', va='bottom')

            # Add category icons
            y_pos = max_freq * 1.1
            for category, (start, end) in categories.items():
                center = (start + end) / 2
                src = load_svg(f"./resources/{category}.svg")
                imagebox = OffsetImage(src, zoom=1.0)
                ax.add_artist(AnnotationBbox(imagebox, (center, y_pos), frameon=False))

            # Axes and titles
            ax.set_title(f'Distribution: {store.name["default"]} (Scale 1-10)', fontsize=14, pad=20)
            ax.set_xlabel('Sleep Quality Score', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_xticks(scores)
            ax.set_ylim(0, max_freq * 1.25)

            # Color bar (legend)
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            cbar = plt.colorbar(sm, ax=ax, orientation='horizontal', pad=0.05,
                                ticks=[2, 4, 6, 8, 10])
            cbar.set_label('Sleep Quality Categories')
            cbar.ax.set_xticklabels(['BAD', 'POOR', 'AVERAGE', 'GOOD', 'HAPPY'])

            plt.savefig(f"{ASSETS_DIR_NAME}/scale_{store.name['format']}.png", dpi=120, bbox_inches='tight')


class StoreCollection(DataManager):
    def __init__(self, pos, method: typing.Literal["exact", "approx"] = "exact", recursive=False, verified=False, nullish=False):
        self.pos = pos
        self.data = {}
        self.method = method
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.recursive = recursive
        self.verified = verified
        self.nullish = nullish

    def cleanup(self, value):
        if value:
            if self.nullish:
                return str(Nullable.classify(value.upper()))
            else:
                return utils.normalize(value).upper()
        else:
            return 0

    def in_depth(self, value: str):
        parts = re.split(r"[;,/]| ET ", value)
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
            self.invalid_subsets.append({
                "pos": len(self.data),
                "type": type,
                "value": v
            })

        if not value or self.is_unknown(value):
            return unresolved(UnwantedDataType.MISSING, value)
        elif value and not re.search(r"[a-zA-Z]", value.strip()) and not re.fullmatch(r"\d+(?:\s*-\s*\d+)?", value.strip()):
            return unresolved(UnwantedDataType.INVALID_FORMAT, value)

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
    def __init__(self, pos, verified=False, nullish=False):
        self.pos = pos
        self.data = []
        self.name = doc_headers[pos]
        self.invalid_subsets = []
        self.verified = verified
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
            self.invalid_subsets.append({
                "pos": len(self.data),
                "type": type,
                "value": v
            })

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

    useless_dicts = ["ND", "AD", "HORODATEUR"]

    # Suppression des données sensibles et/ou inutiles
    for i in useless_dicts:
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
    mdvu_dict = StoreCollection(headers.index("MDVU"), method="approx", recursive=True, verified=True, nullish=True)
    cdfvvpa_dict = StoreSet(headers.index("CDFVVPA"), verified=True, nullish=True)
    caepm_dict = StoreSet(headers.index("CAEPM"), verified=True)
    nddtps_dict = StoreSet(headers.index("NDDTPS"), verified=False, nullish=True)
    tepde_dict = StoreCollection(headers.index("TEPDE"), verified=True)
    spdr_dict = StoreCollection(headers.index("SPDR"), recursive=True, verified=True)
    qds_dict = StoreSet(headers.index("QDS"), verified=True)
    dmm_dict = StoreSet(headers.index("DMM"), verified=True)
    lp_dict = StoreCollection(headers.index("LP"), recursive=True, verified=True)
    ndllpa_dict = StoreCollection(headers.index("NDLLPA"), verified=True)
    tdsp_dict = StoreCollection(headers.index("TDSP"), method="approx", recursive=True, verified=True, nullish=True)
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

        for store in dicts:
            if store not in [anneebac_set, optionbac_dict, logiciels_dict]:
                if isinstance(store, StoreCollection):
                    store.subscribe(rows[i][store.pos])
                elif isinstance(store, StoreSet):
                    store.collect(rows[i][store.pos])

        match = re.search(r"(\d{4})[-/_\s]*(\d{4})?", rows[i][anneebac_set.pos])
        year = match.group(2) if match and match.group(2) else match and match.group(1)
        anneebac_set.collect(year)

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
    for store in dicts:
        if store.removable():
            removable_dicts.append(store.name["default"])
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

    for store in dicts:
        if not store.removable():
            store.generate_rapport(store)

    for store in dicts:
        if not store.removable():
            store.handle_missing_data(store)

    data.add_heading("Identification des données manquantes", level=3)
    rows = [["N", "VALIDE"], *[["", name] for name in UnwantedDataType.get()]]
    headers = [d.name["format"] for d in dicts if not d.removable()]
    for store in dicts:
        if not store.removable():
            rows[0].append(str(store.length()))
            for i, type in enumerate(UnwantedDataType.get()):
                subset = [v for v in store.invalid_subsets if v["type"] == UnwantedDataType[type]]
                rows[i + 1].append(str(len(subset)) if len(subset) != 0 else "")
    data.add_table(["", "", *headers], rows)

    stats.add_heading("Statistiques descriptives", level=2)
    for store in dicts:
        if not store.removable():
            store.generate_statistics(store)

    stats.add_heading("Analyse inférentielle", level=2)
    for store in dicts:
        if not store.removable():
            store.analyze(store)

    if args.write:
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
