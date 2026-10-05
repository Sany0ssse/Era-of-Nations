#!/usr/bin/env python3
"""Apply Jan 1 2000 internet law ideas to history/countries add_ideas blocks."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_DIR = ROOT / "history" / "countries"

INTERNET_LAWS = tuple(f"internet_{i:02d}" for i in range(1, 6))

# Historical internet freedom profiles as of 2000-01-01
# internet_01 = No Internet Censorship
# internet_02 = Limited Internet Censorship
# internet_03 = White Lists
# internet_04 = National Internet (virtually none in 2000; unused at start)
# internet_05 = No Internet
INTERNET_PROFILES = {
    "western_free": "internet_01",
    "nordic": "internet_01",
    "western_microstate": "internet_01",
    "germany_style": "internet_02",
    "japan_style": "internet_02",
    "post_soviet": "internet_01",
    "russia_2000": "internet_01",
    "post_soviet_auth": "internet_03",
    "eastern_eu": "internet_01",
    "eastern_eu_conservative": "internet_01",
    "communist": "internet_03",
    "communist_hard": "internet_05",
    "islamic_theocracy": "internet_02",
    "islamic_hard": "internet_05",
    "islamic_moderate": "internet_02",
    "islamic_secular": "internet_02",
    "asian_democracy": "internet_01",
    "asian_auth": "internet_03",
    "asian_auth_religious": "internet_03",
    "singapore_style": "internet_02",
    "latin_america": "internet_01",
    "latin_conservative": "internet_02",
    "african_democracy": "internet_02",
    "african_auth": "internet_02",
    "african_hard": "internet_03",
    "hierocracy": "internet_01",
    "warlord": "internet_05",
    "rebel_marxist": "internet_02",
    "cartel": "internet_02",
    "india_style": "internet_01",
    "israel_style": "internet_01",
    "lebanon_style": "internet_02",
    "china_tibet": "internet_03",
    "bhutan_style": "internet_05",
    "south_africa": "internet_01",
    "timor_style": "internet_02",
}

PROFILE_TAGS = {
    "western_free": [
        "USA", "CAN", "AUS", "NZL", "ENG", "IRE", "ICE", "HOL", "BEL", "LUX", "AUT", "CHE",
        "ARG", "URG", "COS", "BAR", "JAM", "TRI", "GRA", "STK", "STL", "STV", "DMI", "ANT",
        "CAS", "ASK", "CAL", "TEX", "NYK", "NEN", "FLA", "IDH", "VMT", "WVA", "LKT", "UDT", "USB",
        "CSA", "QUE", "WAS", "SCO", "FLN", "BRI", "NRM", "CAT", "NAV", "GAL", "SPL", "SUL", "PAT",
        "RGD", "YUC", "TAM", "TRC", "ZAP", "BAY", "SAX", "SIL", "PIE", "MIL", "SIC", "SAR", "TUS",
        "NAP", "VNC", "SCL", "SPA", "CRE", "TRA", "WLC", "KSH", "VOJ", "LAG", "EUU",
    ],
    "nordic": ["NOR", "SWE", "FIN", "DEN", "GRL", "FAO"],
    "western_microstate": ["ADO", "SMA", "MNC", "LIC", "IOM", "MON"],
    "germany_style": ["GER", "GDR"],
    "japan_style": ["JAP", "RYU"],
    "russia_2000": [
        "SOV", "RUS", "TAT", "BSH", "BRY", "CHU", "UDM", "MEL", "MOV", "KOM", "KLM", "KCC", "KBK",
        "DAG", "ING", "LEZ", "ADY", "ALT", "KHS", "TUV", "YAK", "YAM", "KHM", "NEE", "CKK", "SIB",
        "CSB", "ESB", "FAR", "GOR", "URA", "KAE", "VTB",
    ],
    "post_soviet": ["EST", "LAT", "LIT", "GEO", "ARM", "AZE", "MLV", "KAZ", "KYR", "TAJ", "UZB", "TRK", "KRP", "SAZ", "TLS"],
    "post_soviet_auth": ["BLR", "TRK"],
    "eastern_eu": ["POL", "CZE", "SLO", "HUN", "ROM", "BUL", "ALB", "FYR", "KOS", "MNT", "SER", "UKR"],
    "eastern_eu_conservative": ["POL", "HUN", "ROM", "BUL", "SER"],
    "communist": ["CHI", "VIE", "LAO", "CUB", "NKO", "TIB", "ETK", "ZAP"],
    "communist_hard": ["NKO", "TAL", "TTP", "ISI", "SHB", "NUS", "AQY"],
    "islamic_theocracy": [
        "PER", "SAU", "TAL", "NEJ", "HEJ", "BRU", "QTF", "HAM", "HEZ", "TTP", "ISI", "SHB", "NUS",
        "AQY", "HOU", "TAL",
    ],
    "islamic_hard": ["TAL", "TTP", "ISI", "SHB", "NUS", "AQY"],
    "islamic_moderate": [
        "AFG", "PAK", "BAN", "MOR", "TUN", "ALG", "LBA", "SUD", "YEM", "OMA", "QAT", "BHR", "KUW",
        "UAE", "JOR", "EGY", "IRQ", "SYR", "MLD", "COM", "SOM", "SML", "PUN", "JUB", "SWS", "SNA",
        "MAU", "GNC", "HOR", "GNA", "CYR", "TRP", "FEZ", "TIE", "TUA", "SAO", "GUB", "GUI", "SEN",
        "NGR", "CHA", "DJI",
    ],
    "islamic_secular": ["TUR", "AZE", "KAZ", "KYR", "UZB", "TAJ", "IND"],
    "asian_democracy": [
        "KOR", "TAI", "SIA", "PHI", "IND", "MAY", "NEP", "BHU", "BAN", "SRI", "FIJ", "SAM", "TON",
        "TUL", "NAU", "KIR", "MIC", "MAR", "PAU", "SOL", "VAN", "TLS", "TIM",
    ],
    "asian_auth": ["SIN", "HKG", "MAC", "MMR", "KHM", "CBD", "VIE", "CHI"],
    "singapore_style": ["SIN"],
    "latin_america": ["BRA", "MEX", "COL", "CHL", "ECU", "BOL", "PAR", "PER", "VEN", "GUA", "HON", "ELS", "NIC", "PAN", "DOM", "HTI", "SUR", "GUY", "FGU", "BLZ", "CUB"],
    "latin_conservative": ["GUA", "HON", "NIC", "HTI"],
    "african_democracy": [
        "SAF", "BOT", "NAM", "GAH", "KEN", "SEN", "BEN", "MLW", "ZAM", "MRT", "SEY", "VER", "STH",
        "LES", "SWA", "GAB", "GAM", "GUB", "SIE", "LIB", "NIG", "CAM", "ETH", "ERI", "MAD", "MOZ",
        "TNZ", "UGA", "RWA", "BUR", "ZIM", "AGL",
    ],
    "african_auth": [
        "EGY", "LBA", "DRC", "CNG", "CAR", "CHA", "EGU", "GUB", "GUI", "CDI", "BFA", "NGR", "SUD",
        "SSU", "SOM", "DJI", "GAB", "CAM", "ZIM", "UGA", "RWA", "BUR", "ERI", "ETH", "MOR", "DAR",
        "SHA", "CAB", "UNI", "RCD", "MLC", "FNC", "AFR", "BAL", "SEL", "LOG", "CSM",
    ],
    "hierocracy": ["HLS"],
    "warlord": [
        "AFG", "SOM", "LUR", "PKK", "PUK", "ROJ", "KUR", "IKR", "IEK", "FSA", "ALA", "DRU", "WAG",
        "SLA", "CHS", "KAC", "KAR", "SHN", "NHN", "WAA", "ACE", "BDA", "BAL", "CAR", "DRC", "MLC",
        "RCD", "FNC", "SEL", "LOG", "PUN", "JUB", "SNA", "SWS", "SML", "NPM", "ZAP", "RUS",
    ],
    "rebel_marxist": ["NPM", "ZAP", "FAR"],
    "cartel": ["SLA", "TRC", "TAM"],
    "india_style": ["RAJ", "PAK", "KAS", "MAN", "SIK", "MEG", "KHA", "KAM", "LAD", "ARK", "CHS", "NPM"],
    "israel_style": ["ISR"],
    "lebanon_style": ["LEB"],
    "china_tibet": ["TIB", "ETK"],
    "bhutan_style": ["BHU"],
    "south_africa": ["SAF"],
    "timor_style": ["TIM", "TLS"],
}

TAG_INTERNET = {}
for profile, tags in PROFILE_TAGS.items():
    law = INTERNET_PROFILES[profile]
    for tag in tags:
        TAG_INTERNET[tag] = law

OVERRIDES = {
    # Explicit Jan 1 2000 historical accuracy
    "SOV": "internet_01",
    "RUS": "internet_01",
    "USA": "internet_01",
    "ENG": "internet_01",
    "FRA": "internet_01",
    "GER": "internet_02",
    "HOL": "internet_01",
    "NOR": "internet_01",
    "SWE": "internet_01",
    "FIN": "internet_01",
    "DEN": "internet_01",
    "CHI": "internet_03",
    "NKO": "internet_05",
    "CUB": "internet_03",
    "VIE": "internet_03",
    "LAO": "internet_03",
    "PER": "internet_02",
    "SAU": "internet_02",
    "TAL": "internet_05",
    "AFG": "internet_05",
    "TUR": "internet_02",
    "ISR": "internet_01",
    "EGY": "internet_02",
    "JAP": "internet_02",
    "KOR": "internet_01",
    "TAI": "internet_01",
    "SIN": "internet_02",
    "IND": "internet_01",
    "RAJ": "internet_01",
    "PAK": "internet_02",
    "BRA": "internet_01",
    "MEX": "internet_01",
    "SAF": "internet_01",
    "HLS": "internet_01",
    "BLR": "internet_01",
    "TRK": "internet_03",
    "UZB": "internet_03",
    "YEM": "internet_02",
    "IRQ": "internet_02",
    "SYR": "internet_02",
    "LBA": "internet_03",
    "SUD": "internet_03",
    "ZWE": "internet_02",
    "ZIM": "internet_02",
    "CHL": "internet_01",
    "POL": "internet_01",
    "HUN": "internet_01",
    "ROM": "internet_01",
    "BUL": "internet_01",
    "UKR": "internet_01",
    "CHE": "internet_05",
    "TIB": "internet_03",
    "ETK": "internet_03",
    "BHU": "internet_05",
    "TIM": "internet_02",
    "PAL": "internet_02",
    "LEB": "internet_02",
    "JOR": "internet_02",
    "MOR": "internet_02",
    "TUN": "internet_02",
    "ALG": "internet_03",
    "MMR": "internet_03",
    "BRM": "internet_03",
    "SIA": "internet_02",
    "MAY": "internet_02",
    "HKG": "internet_01",
    "MAC": "internet_01",
    "NEP": "internet_02",
    "BAN": "internet_02",
    "SRI": "internet_02",
    "PHI": "internet_01",
    "PTR": "internet_01",
    "NLA": "internet_01",
    "SOM": "internet_05",
    "ERI": "internet_02",
    "MMR": "internet_03",
    "CBD": "internet_02",
    "KHM": "internet_02",
    "UAE": "internet_02",
    "KUW": "internet_02",
    "QAT": "internet_02",
    "BHR": "internet_02",
    "OMA": "internet_02",
    "BRU": "internet_02",
    "MLD": "internet_02",
    "EUU": "internet_01",
    "ISI": "internet_05",
    "SHB": "internet_05",
    "NUS": "internet_05",
    "AQY": "internet_05",
    "TTP": "internet_05",
    "HAM": "internet_02",
    "HEZ": "internet_02",
    "HOU": "internet_02",
    "DRC": "internet_02",
    "CNG": "internet_02",
    "CAR": "internet_05",
    "LUR": "internet_05",
    "SSU": "internet_02",
    "DAR": "internet_02",
    "ETH": "internet_02",
    "KAZ": "internet_01",
    "GEO": "internet_01",
    "ARM": "internet_01",
    "AZE": "internet_01",
    "EST": "internet_01",
    "LAT": "internet_01",
    "LIT": "internet_01",
    "MLV": "internet_01",
    "KYR": "internet_01",
    "TAJ": "internet_02",
    "UKR": "internet_01",
    "CRO": "internet_01",
    "SLO": "internet_01",
    "CZE": "internet_01",
    "SVK": "internet_01",
    "BOS": "internet_01",
    "SER": "internet_01",
    "MNT": "internet_01",
    "ALB": "internet_01",
    "KOS": "internet_01",
    "SPR": "internet_01",
    "POR": "internet_01",
    "ITA": "internet_01",
    "GRE": "internet_01",
    "CYP": "internet_01",
    "AUT": "internet_01",
    "SWI": "internet_01",
    "BEL": "internet_01",
    "LUX": "internet_01",
    "ICE": "internet_01",
    "IRE": "internet_01",
    "CAN": "internet_01",
    "AUS": "internet_01",
    "NZL": "internet_01",
}
TAG_INTERNET.update(OVERRIDES)

DEFAULT_INTERNET = "internet_02"

INTERNET_LAW_RE = re.compile(r"^\s*(internet_0[1-5])\s*$")
FREEDOM_LAW_RE = re.compile(
    r"^\s*(censorship_0[1-4]|assembly_0[1-3]|freedom_religion_0[1-4]|"
    r"lgbt_laws_0[1-4]|freedom_trade_unions_0[1-4])\s*$"
)


def extract_tag(filename: str) -> str:
    return filename.split(" - ")[0].strip()


def strip_existing_internet(block_body: str) -> str:
    lines = block_body.splitlines(keepends=True)
    return "".join(line for line in lines if not INTERNET_LAW_RE.match(line.strip()))


def insert_internet_law(block_body: str, law: str) -> str:
    body = strip_existing_internet(block_body)
    lines = body.splitlines(keepends=True)
    out = []
    inserted = False

    for line in lines:
        out.append(line)
        if not inserted and FREEDOM_LAW_RE.match(line.strip()):
            # Peek ahead: insert after the last consecutive freedom law line
            continue

    # Second pass: find last freedom law and insert after it
    out = []
    last_freedom_idx = -1
    for i, line in enumerate(lines):
        if FREEDOM_LAW_RE.match(line.strip()):
            last_freedom_idx = i

    if last_freedom_idx >= 0:
        for i, line in enumerate(lines):
            out.append(line)
            if i == last_freedom_idx:
                out.append(f"\t\t{law}\n")
                inserted = True
    else:
        # No freedom laws block yet — prepend under #Freedom Laws if present
        for i, line in enumerate(lines):
            out.append(line)
            if not inserted and "#Freedom Laws" in line:
                out.append(f"\t\t{law}\n")
                inserted = True
        if not inserted:
            header = "\t\t#Freedom Laws\n"
            out = [header, f"\t\t{law}\n", *lines]

    return "".join(out)


def find_block_end(text: str, open_brace_index: int) -> int:
    brace = 0
    for i in range(open_brace_index, len(text)):
        if text[i] == "{":
            brace += 1
        elif text[i] == "}":
            brace -= 1
            if brace == 0:
                return i + 1
    raise ValueError("Unclosed block")


def replace_add_ideas_blocks(section: str, law: str) -> str:
    result = []
    pos = 0
    pattern = re.compile(r"add_ideas\s*=\s*\{")
    while True:
        match = pattern.search(section, pos)
        if not match:
            result.append(section[pos:])
            break
        result.append(section[pos:match.start()])
        brace_start = match.end() - 1
        brace_end = find_block_end(section, brace_start)
        header = section[match.start():brace_start + 1]
        body = section[brace_start + 1:brace_end - 1]
        closing = section[brace_end - 1:brace_end]
        new_body = insert_internet_law(body, law)
        result.append(header + new_body + closing)
        pos = brace_end
    return "".join(result)


def process_file(path: Path, law: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if "2000.1.1" not in text:
        return False

    start = text.find("2000.1.1 = {")
    if start == -1:
        return False

    block_open = text.find("{", start)
    block_end = find_block_end(text, block_open)
    block = text[block_open:block_end]
    if "add_ideas" not in block:
        return False

    new_block = replace_add_ideas_blocks(block, law)
    if new_block == block:
        return False

    new_text = text[:block_open] + new_block + text[block_end:]
    path.write_text(new_text, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    updated = 0
    skipped = []
    no_2000 = []

    for path in sorted(COUNTRIES_DIR.glob("*.txt")):
        tag = extract_tag(path.name)
        law = TAG_INTERNET.get(tag, DEFAULT_INTERNET)
        content = path.read_text(encoding="utf-8")

        if "2000.1.1" not in content:
            continue
        if "add_ideas" not in content:
            no_2000.append(tag)
            continue

        if process_file(path, law):
            updated += 1
        else:
            skipped.append(tag)

    print(f"Updated {updated} files")
    if skipped:
        print(f"Skipped (no change / parse issue): {len(skipped)} tags")
    if no_2000:
        print(f"No add_ideas in 2000 block: {len(no_2000)} tags")


if __name__ == "__main__":
    main()
