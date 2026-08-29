# Administrative subdivisions of Benin: 12 départements, 77 communes (1999 reform).
# Commune list and HASC department codes from Statoids (2002 census / Atlas Monographique).
# https://www.statoids.com/ybj.html

DEPT_CODE_TO_NAME = {
    "AL": "Alibori",
    "AK": "Atacora",
    "AQ": "Atlantique",
    "BO": "Borgou",
    "CL": "Collines",
    "CF": "Couffo",
    "DO": "Donga",
    "LI": "Littoral",
    "MO": "Mono",
    "OU": "Ouémé",
    "PL": "Plateau",
    "ZO": "Zou",
}

# Approximate department centroids (decimal degrees) for demo map coordinates.
DEPT_CENTROIDS = {
    "AL": (11.13, 2.94),
    "AK": (10.37, 1.37),
    "AQ": (6.45, 2.35),
    "BO": (9.35, 2.62),
    "CL": (7.95, 2.18),
    "CF": (7.02, 1.72),
    "DO": (9.70, 1.72),
    "LI": (6.37, 2.43),
    "MO": (6.85, 1.78),
    "OU": (6.48, 2.62),
    "PL": (7.05, 2.58),
    "ZO": (7.25, 2.08),
}


def _jitter(name: str, base_lat: float, base_lon: float) -> tuple[float, float]:
    """Stable small offset from commune name so coordinates differ without external geocoding."""
    h = hash(name) % 10000
    return base_lat + (h % 200 - 100) / 5000.0, base_lon + (h // 200 % 200 - 100) / 5000.0


# (department HASC code, official commune name)
COMMUNES: list[tuple[str, str]] = [
    ("ZO", "Abomey"),
    ("AQ", "Abomey-Calavi"),
    ("PL", "Adja-Ouèrè"),
    ("OU", "Adjarra"),
    ("OU", "Adjohoun"),
    ("ZO", "Agbangnizoun"),
    ("OU", "Aguégués"),
    ("OU", "Akpro-Missérété"),
    ("AQ", "Allada"),
    ("CF", "Aplahoué"),
    ("MO", "Athiémé"),
    ("OU", "Avrankou"),
    ("AL", "Banikoara"),
    ("CL", "Bantè"),
    ("DO", "Bassila"),
    ("BO", "Bembéréké"),
    ("ZO", "Bohicon"),
    ("OU", "Bonou"),
    ("MO", "Bopa"),
    ("AK", "Boukoumbé"),
    ("AK", "Cobly"),
    ("MO", "Comè"),
    ("DO", "Copargo"),
    ("LI", "Cotonou"),
    ("ZO", "Covè"),
    ("OU", "Dangbo"),
    ("CL", "Dassa-Zoumè"),
    ("CF", "Djakotomey"),
    ("ZO", "Djidja"),
    ("DO", "Djougou"),
    ("CF", "Dogbo"),
    ("CL", "Glazoué"),
    ("AL", "Gogounou"),
    ("MO", "Grand-Popo"),
    ("MO", "Houéyogbé"),
    ("PL", "Ifangni"),
    ("BO", "Kalalé"),
    ("AL", "Kandi"),
    ("AL", "Karimama"),
    ("AK", "Kérou"),
    ("PL", "Kétou"),
    ("CF", "Klouékanmè"),
    ("AK", "Kouandé"),
    ("AQ", "Kpomassè"),
    ("CF", "Lalo"),
    ("MO", "Lokossa"),
    ("AL", "Malanville"),
    ("AK", "Matéri"),
    ("AK", "Natitingou"),
    ("BO", "N'Dali"),
    ("BO", "Nikki"),
    ("DO", "Ouaké"),
    ("CL", "Ouèssè"),
    ("AQ", "Ouidah"),
    ("ZO", "Ouinhi"),
    ("BO", "Parakou"),
    ("AK", "Péhunco"),
    ("BO", "Pèrèrè"),
    ("PL", "Pobè"),
    ("OU", "Porto-Novo"),
    ("PL", "Sakété"),
    ("CL", "Savalou"),
    ("CL", "Savè"),
    ("AL", "Segbana"),
    ("OU", "Sèmè-Kpodji"),
    ("BO", "Sinendé"),
    ("AQ", "Sô-Ava"),
    ("AK", "Tanguiéta"),
    ("BO", "Tchaourou"),
    ("AQ", "Toffo"),
    ("AQ", "Tori-Bossito"),
    ("AK", "Toucountouna"),
    ("CF", "Toviklin"),
    ("ZO", "Zagnanado"),
    ("ZO", "Za-Kpota"),
    ("AQ", "Zè"),
    ("ZO", "Zogbodomey"),
]


def commune_coordinates(dept_code: str, commune_name: str) -> tuple[float, float]:
    base = DEPT_CENTROIDS[dept_code]
    return _jitter(commune_name, base[0], base[1])
