"""Frozen make/model lexicon and the matcher that produces the primary outcome.

The primary outcome (`headline_names_make`) is computed mechanically by this module.
No human judgment about whether a headline "emphasises" a brand enters the primary
outcome — that is deliberate (Protocol section 8.1).

FREEZE POINT: this file is frozen at Phase 2 registration. After that, changes require
a dated entry in CODEBOOK.md section 5 and a re-run over the full dataset.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# --- exposure groups (Protocol section 7.1) --------------------------------------

TESLA = "tesla"
OTHER_BEV = "other_bev"
PREMIUM_ICE = "premium_ice"
MAINSTREAM_ICE = "mainstream_ice"


@dataclass(frozen=True)
class Make:
    canonical: str
    group: str
    aliases: tuple[str, ...] = ()
    #: Model tokens that identify this make unambiguously to an Australian reader.
    #: Ambiguous tokens are listed in AMBIGUOUS_MODEL_TOKENS and deliberately omitted.
    models: tuple[str, ...] = ()


MAKES: tuple[Make, ...] = (
    Make("Tesla", TESLA,
         aliases=("Tesla",),
         models=("Model 3", "Model Y", "Model S", "Model X", "Cybertruck", "Roadster")),

    # --- other battery-electric makes -------------------------------------------
    Make("BYD", OTHER_BEV, aliases=("BYD",), models=("Atto 3", "Seal", "Dolphin", "Sealion", "Shark")),
    Make("Polestar", OTHER_BEV, aliases=("Polestar",), models=()),
    Make("Nissan", MAINSTREAM_ICE, aliases=("Nissan",), models=("Leaf", "Navara", "Patrol", "Qashqai", "X-Trail")),
    Make("Volvo", PREMIUM_ICE, aliases=("Volvo",), models=()),
    Make("Cupra", OTHER_BEV, aliases=("Cupra",), models=()),
    Make("GWM", MAINSTREAM_ICE, aliases=("GWM", "Great Wall"), models=("Haval", "Cannon", "Tank")),
    Make("Zeekr", OTHER_BEV, aliases=("Zeekr",), models=()),
    Make("Xpeng", OTHER_BEV, aliases=("Xpeng",), models=()),

    # --- premium / luxury internal combustion (and their EVs) --------------------
    Make("BMW", PREMIUM_ICE, aliases=("BMW",), models=()),
    Make("Mercedes-Benz", PREMIUM_ICE, aliases=("Mercedes-Benz", "Mercedes", "Merc"), models=()),
    Make("Audi", PREMIUM_ICE, aliases=("Audi",), models=()),
    Make("Porsche", PREMIUM_ICE, aliases=("Porsche",), models=("Cayenne", "Macan", "Taycan", "911")),
    Make("Land Rover", PREMIUM_ICE, aliases=("Land Rover", "Range Rover", "Landrover"),
         models=("Defender", "Discovery", "Evoque")),
    Make("Lexus", PREMIUM_ICE, aliases=("Lexus",), models=()),
    Make("Jaguar", PREMIUM_ICE, aliases=("Jaguar",), models=()),
    Make("Maserati", PREMIUM_ICE, aliases=("Maserati",), models=()),
    Make("Ferrari", PREMIUM_ICE, aliases=("Ferrari",), models=()),
    Make("Lamborghini", PREMIUM_ICE, aliases=("Lamborghini", "Lambo"), models=("Urus", "Huracan", "Aventador")),
    Make("Bentley", PREMIUM_ICE, aliases=("Bentley",), models=()),
    Make("Aston Martin", PREMIUM_ICE, aliases=("Aston Martin",), models=()),
    Make("McLaren", PREMIUM_ICE, aliases=("McLaren",), models=()),
    Make("Genesis", PREMIUM_ICE, aliases=("Genesis",), models=()),

    # --- mainstream internal combustion ------------------------------------------
    Make("Toyota", MAINSTREAM_ICE, aliases=("Toyota",),
         models=("HiLux", "LandCruiser", "Land Cruiser", "Corolla", "Camry", "Prado",
                 "Kluger", "RAV4", "Yaris", "Hiace", "Tarago")),
    Make("Mazda", MAINSTREAM_ICE, aliases=("Mazda",), models=("CX-5", "CX-3", "CX-9", "BT-50")),
    Make("Hyundai", MAINSTREAM_ICE, aliases=("Hyundai",), models=("Tucson", "Santa Fe", "i30", "Ioniq", "Elantra")),
    Make("Kia", MAINSTREAM_ICE, aliases=("Kia",), models=("Sportage", "Sorento", "Carnival", "Cerato", "Stinger", "EV6")),
    Make("Ford", MAINSTREAM_ICE, aliases=("Ford",), models=("Ranger", "Falcon", "Mustang", "Raptor")),
    Make("Mitsubishi", MAINSTREAM_ICE, aliases=("Mitsubishi",), models=("Triton", "Outlander", "Pajero", "ASX", "Lancer")),
    Make("Subaru", MAINSTREAM_ICE, aliases=("Subaru",), models=("Forester", "Outback", "WRX", "Liberty", "Impreza")),
    Make("Holden", MAINSTREAM_ICE, aliases=("Holden",), models=("Commodore", "Barina", "Ute")),
    Make("Volkswagen", MAINSTREAM_ICE, aliases=("Volkswagen", "VW", "Volkswagon"),
         models=("Golf", "Tiguan", "Amarok", "Passat", "Polo")),
    Make("Honda", MAINSTREAM_ICE, aliases=("Honda",), models=("Accord", "HR-V", "CR-V")),
    Make("Isuzu", MAINSTREAM_ICE, aliases=("Isuzu",), models=("D-Max", "MU-X")),
    Make("MG", MAINSTREAM_ICE, aliases=("MG",), models=("ZS", "MG3", "MG4", "HS")),
    Make("Jeep", MAINSTREAM_ICE, aliases=("Jeep",), models=("Wrangler", "Cherokee", "Grand Cherokee")),
    Make("Suzuki", MAINSTREAM_ICE, aliases=("Suzuki",), models=("Swift", "Vitara", "Jimny")),
    Make("Renault", MAINSTREAM_ICE, aliases=("Renault",), models=("Koleos", "Megane")),
    Make("Peugeot", MAINSTREAM_ICE, aliases=("Peugeot",), models=()),
    Make("Skoda", MAINSTREAM_ICE, aliases=("Skoda",), models=("Octavia", "Kodiaq")),
    Make("SsangYong", MAINSTREAM_ICE, aliases=("SsangYong",), models=("Musso", "Rexton")),
    Make("LDV", MAINSTREAM_ICE, aliases=("LDV",), models=()),
    Make("Chrysler", MAINSTREAM_ICE, aliases=("Chrysler",), models=()),
    Make("Dodge", MAINSTREAM_ICE, aliases=("Dodge",), models=()),
    Make("RAM", MAINSTREAM_ICE, aliases=("RAM",), models=()),
    Make("Chevrolet", MAINSTREAM_ICE, aliases=("Chevrolet", "Chevy"), models=("Silverado",)),
)

#: Model tokens EXCLUDED from the lexicon because they are ordinary words, place names,
#: or otherwise ambiguous in Australian headline usage (Codebook section 3.2). Excluding
#: them costs sensitivity; including them would cost specificity, and a false positive on
#: a non-Tesla make biases the study toward its own hypothesis.
AMBIGUOUS_MODEL_TOKENS: frozenset[str] = frozenset({
    "Focus", "Escape", "Territory", "Fit", "City", "Civic", "Insight", "Odyssey",
    "Colorado", "Everest", "Captiva", "Cruze", "Astra", "Jazz", "Spark", "Kona",
    "Sonata", "Equinox", "Traverse", "Trailblazer", "Pilot", "Legend", "Express",
    "Accent", "Venue", "Seltos", "Soul", "Rio", "Picanto", "Getz", "Excel",
})

#: Rejection contexts (Codebook section 3.3). A token match is rejected if any of these
#: patterns matches the surrounding window. Each is a real false positive class.
NEGATIVE_CONTEXTS: dict[str, tuple[str, ...]] = {
    "tesla": (
        r"\btesla\s+coil\b",
        r"\bnikola\s+tesla\b",
        r"\btesla\s+(inc|motors|shares?|stock|share\s+price|earnings|factory|gigafactory|recall)\b",
        r"\b(elon\s+musk|musk)\b.{0,20}\btesla\b",
        r"\b\d+(\.\d+)?\s*tesla\b",          # magnetic flux density, e.g. "3 tesla MRI"
        r"\btesla\s+(mri|scanner|magnet)\b",
    ),
    "ranger": (r"\b(park|parks|national\s+park|power|army|texas)\s+rangers?\b", r"\brangers?\s+(said|found|warned)\b"),
    "kia": (r"\bkia\s+ora\b",),
    "polestar": (r"\bpole\s+star\b",),
    "mg": (r"\b\d+\s*mg\b", r"\bmg/(kg|ml|l|dl)\b"),
    "ram": (r"\bram\s+(raid|raider|raiders|into|through)\b", r"\bbattering\s+ram\b"),
    "jaguar": (r"\bjaguar\s+(cub|attack|enclosure|zoo)\b",),
    "genesis": (r"\bgenesis\s+(of|block|energy)\b", r"\bbook\s+of\s+genesis\b"),
    "911": (r"\b911\s+(call|calls|operator|dispatch|emergency)\b", r"\bseptember\s+11\b"),
    "defender": (r"\b(human\s+rights|title|premiership|cup)\s+defender\b", r"\bdefenders?\s+of\b"),
    "discovery": (r"\bdiscovery\s+(channel|of|that)\b", r"\bmade\s+the\s+discovery\b"),
    "outback": (r"\bthe\s+outback\b", r"\boutback\s+(town|road|highway|queensland|nsw|australia|pub)\b"),
    "liberty": (r"\bliberty\s+(party|street|university)\b",),
    "shark": (r"\bshark\s+(attack|bite|net|nets|sighting)\b",),
    "seal": (r"\bseal\s+(pup|colony|team)\b",),
    "dolphin": (r"\bdolphins?\s+(pod|beached|nrl)\b",),
    "tank": (r"\b(water|fuel|fish|septic|petrol|army)\s+tanks?\b",),
    "cannon": (r"\bcannon\s+(hill|fire|ball)\b",),
    "mustang": (r"\bwild\s+mustangs?\b",),
    "raptor": (r"\braptors?\s+(bird|nest|species)\b", r"\btoronto\s+raptors\b"),
    "swift": (r"\btaylor\s+swift\b", r"\bswift\s+(action|response|justice|current)\b"),
    "wrangler": (r"\bwrangler\s+jeans\b",),
}

_WINDOW = 40  # characters either side of a match inspected for rejection context


def normalise(text: str) -> str:
    """Fold text to the canonical form the matcher operates on.

    NFKD-normalise, flatten curly quotes and dashes, collapse whitespace, lowercase.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = (text.replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-").replace("−", "-"))
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def _token_pattern(token: str) -> re.Pattern[str]:
    """Whole-token regex allowing plurals, possessives, and space/hyphen flexibility.

    'Model 3' matches 'model 3' and 'model-3'; 'Tesla' matches 'teslas' and "tesla's"
    but not 'teslarati'.
    """
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", token.lower()) if p]
    body = r"[\s\-]*".join(parts) if len(parts) > 1 else parts[0]
    return re.compile(rf"(?<![\w]){body}(?:'s|s'|s)?(?![\w])")


@dataclass
class _CompiledMake:
    make: Make
    make_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    model_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)


def _compile() -> dict[str, _CompiledMake]:
    out: dict[str, _CompiledMake] = {}
    for m in MAKES:
        cm = _CompiledMake(m)
        for a in m.aliases:
            cm.make_patterns.append((a.lower(), _token_pattern(a)))
        for mod in m.models:
            if mod in AMBIGUOUS_MODEL_TOKENS:
                raise ValueError(f"{mod!r} is on the ambiguous list but used as a model token")
            cm.model_patterns.append((mod.lower(), _token_pattern(mod)))
        out[m.canonical] = cm
    return out


_COMPILED = _compile()

#: Canonical make name for every alias, for normalising coded data (Codebook section 1.4).
ALIAS_TO_MAKE: dict[str, str] = {
    a.lower(): m.canonical for m in MAKES for a in m.aliases
}
MAKE_GROUP: dict[str, str] = {m.canonical: m.group for m in MAKES}


def canonical_make(raw: str) -> str | None:
    """Normalise a coded make string (Codebook section 1.4). None if unrecognised."""
    return ALIAS_TO_MAKE.get(normalise(raw))


def _rejected(token: str, text: str, start: int, end: int) -> bool:
    patterns = NEGATIVE_CONTEXTS.get(token)
    if not patterns:
        return False
    window = text[max(0, start - _WINDOW): end + _WINDOW]
    return any(re.search(p, window) for p in patterns)


def find_make_mentions(text: str, *, strict: bool = False) -> dict[str, list[str]]:
    """Return {canonical make: [matched tokens]} for every make identified in `text`.

    strict=True restricts matching to make tokens only, excluding model tokens — the
    pre-specified sensitivity definition of the primary outcome (Protocol section 7.3).
    """
    t = normalise(text)
    if not t:
        return {}
    hits: dict[str, list[str]] = {}
    for canonical, cm in _COMPILED.items():
        pats = cm.make_patterns if strict else cm.make_patterns + cm.model_patterns
        for token, pat in pats:
            for m in pat.finditer(t):
                if _rejected(token, t, m.start(), m.end()):
                    continue
                hits.setdefault(canonical, []).append(token)
                break
    return hits


def names_make(text: str, make: str, *, strict: bool = False) -> bool:
    """Primary outcome: does `text` identify `make`?

    `make` may be any alias; it is canonicalised first.
    """
    canonical = canonical_make(make) or make
    return canonical in find_make_mentions(text, strict=strict)


def identified_makes(text: str, *, strict: bool = False) -> set[str]:
    """Every make identified in `text`. Used for the multi-vehicle matched analysis."""
    return set(find_make_mentions(text, strict=strict))
