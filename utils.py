from unicodedata import normalize as normalize_unicode


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