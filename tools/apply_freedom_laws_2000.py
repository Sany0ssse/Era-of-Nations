#!/usr/bin/env python3
"""Apply Jan 1 2000 freedom law ideas to history/countries add_ideas blocks."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COUNTRIES_DIR = ROOT / "history" / "countries"

LAW_NAMES = (
    "censorship_01", "censorship_02", "censorship_03", "censorship_04",
    "assembly_01", "assembly_02", "assembly_03",
    "freedom_religion_01", "freedom_religion_02", "freedom_religion_03", "freedom_religion_04",
    "lgbt_laws_01", "lgbt_laws_02", "lgbt_laws_03", "lgbt_laws_04",
    "freedom_trade_unions_01", "freedom_trade_unions_02", "freedom_trade_unions_03", "freedom_trade_unions_04",
)

# Named profiles: (censorship, assembly, religion, lgbt, trade_unions)
P = {
    "western_free": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_02", "freedom_trade_unions_02"),
    "western_traditional_lgbt": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "nordic": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_02", "freedom_trade_unions_01"),
    "western_microstate": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "germany_style": ("censorship_02", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "japan_style": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "post_soviet": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "russia_2000": ("censorship_01", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "post_soviet_auth": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_03"),
    "eastern_eu": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "eastern_eu_conservative": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "communist": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_03"),
    "communist_hard": ("censorship_04", "assembly_03", "freedom_religion_01", "lgbt_laws_04", "freedom_trade_unions_04"),
    "islamic_theocracy": ("censorship_03", "assembly_03", "freedom_religion_04", "lgbt_laws_04", "freedom_trade_unions_03"),
    "islamic_hard": ("censorship_04", "assembly_03", "freedom_religion_04", "lgbt_laws_04", "freedom_trade_unions_04"),
    "islamic_moderate": ("censorship_02", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "islamic_secular": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "asian_democracy": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "asian_auth": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_03"),
    "asian_auth_religious": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "singapore_style": ("censorship_02", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_03"),
    "latin_america": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "latin_conservative": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "african_democracy": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_02"),
    "african_auth": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "african_hard": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_04"),
    "hierocracy": ("censorship_03", "assembly_03", "freedom_religion_04", "lgbt_laws_04", "freedom_trade_unions_04"),
    "warlord": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_04"),
    "rebel_marxist": ("censorship_03", "assembly_03", "freedom_religion_01", "lgbt_laws_03", "freedom_trade_unions_03"),
    "cartel": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_04"),
    "india_style": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_02"),
    "israel_style": ("censorship_02", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "lebanon_style": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "china_tibet": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_03", "freedom_trade_unions_03"),
    "bhutan_style": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_04"),
    "south_africa": ("censorship_02", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "timor_style": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_02"),
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
    "western_traditional_lgbt": ["FRA", "ITA", "POR", "SPR", "GRE", "CYP", "NCY", "MLT", "CRO", "SLV", "SLO", "BOS", "HZG", "RSK", "PMR", "CRM", "NOV", "DPR", "LPR", "DRP", "LRP", "PRP", "VRP", "OPR", "HPR", "MLR", "KUB", "DON", "GGZ", "ADJ", "ABK", "SOO", "NKR", "ARW"],
    "japan_style": ["JAP", "RYU"],
    "russia_2000": ["SOV", "RUS", "TAT", "BSH", "BRY", "CHU", "UDM", "MEL", "MOV", "KOM", "KLM", "KCC", "KBK", "DAG", "ING", "LEZ", "ADY", "ALT", "KHS", "TUV", "YAK", "YAM", "KHM", "NEE", "CKK", "SIB", "CSB", "ESB", "FAR", "GOR", "URA", "KAE", "VTB"],
    "post_soviet": ["EST", "LAT", "LIT", "GEO", "ARM", "AZE", "MLV", "KAZ", "KYR", "TAJ", "UZB", "TRK", "KRP", "SAZ", "TLS"],
    "post_soviet_auth": ["BLR", "TRK"],
    "eastern_eu": ["POL", "CZE", "SLO", "HUN", "ROM", "BUL", "ALB", "FYR", "KOS", "MNT", "SER", "UKR"],
    "eastern_eu_conservative": ["POL", "HUN", "ROM", "BUL", "SER"],
    "communist": ["CHI", "VIE", "LAO", "CUB", "NKO", "TIB", "ETK", "ZAP"],
    "communist_hard": ["NKO", "TAL", "TTP", "ISI", "SHB", "NUS", "AQY"],
    "islamic_theocracy": ["PER", "SAU", "TAL", "NEJ", "HEJ", "BRU", "QTF", "HAM", "HEZ", "TTP", "ISI", "SHB", "NUS", "AQY", "HOU", "TAL"],
    "islamic_hard": ["TAL", "TTP", "ISI", "SHB", "NUS", "AQY"],
    "islamic_moderate": ["AFG", "PAK", "BAN", "MOR", "TUN", "ALG", "LBA", "SUD", "YEM", "OMA", "QAT", "BHR", "KUW", "UAE", "JOR", "EGY", "IRQ", "SYR", "MLD", "COM", "SOM", "SML", "PUN", "JUB", "SWS", "SNA", "MAU", "GNC", "HOR", "GNA", "CYR", "TRP", "FEZ", "TIE", "TUA", "SAO", "GUB", "GUI", "SEN", "NGR", "CHA", "DJI"],
    "islamic_secular": ["TUR", "AZE", "KAZ", "KYR", "UZB", "TAJ", "IND"],
    "asian_democracy": ["KOR", "TAI", "SIA", "PHI", "IND", "MAY", "NEP", "BHU", "BAN", "SRI", "FIJ", "SAM", "TON", "TUL", "NAU", "KIR", "MIC", "MAR", "PAU", "SOL", "VAN", "TLS", "TIM"],
    "asian_auth": ["SIN", "HKG", "MAC", "MMR", "KHM", "CBD", "VIE", "CHI"],
    "singapore_style": ["SIN"],
    "latin_america": ["BRA", "MEX", "COL", "CHL", "ECU", "BOL", "PAR", "PER", "VEN", "GUA", "HON", "ELS", "NIC", "PAN", "DOM", "HTI", "SUR", "GUY", "FGU", "BLZ", "CUB"],
    "latin_conservative": ["GUA", "HON", "NIC", "HTI"],
    "african_democracy": ["SAF", "BOT", "NAM", "GAH", "KEN", "SEN", "BEN", "MLW", "ZAM", "MRT", "SEY", "VER", "STH", "LES", "SWA", "GAB", "GAM", "GUB", "SIE", "LIB", "NIG", "CAM", "ETH", "ERI", "MAD", "MOZ", "TNZ", "UGA", "RWA", "BUR", "ZIM", "AGL"],
    "african_auth": ["EGY", "LBA", "DRC", "CNG", "CAR", "CHA", "EGU", "GUB", "GUI", "CDI", "BFA", "NGR", "SUD", "SSU", "SOM", "DJI", "GAB", "CAM", "ZIM", "UGA", "RWA", "BUR", "ERI", "ETH", "MOR", "DAR", "SHA", "CAB", "UNI", "RCD", "MLC", "FNC", "AFR", "BAL", "SEL", "LOG", "CSM"],
    "hierocracy": ["HLS"],
    "warlord": ["AFG", "SOM", "LUR", "PKK", "PUK", "ROJ", "KUR", "IKR", "IEK", "FSA", "ALA", "DRU", "WAG", "SLA", "CHS", "KAC", "KAR", "SHN", "NHN", "WAA", "ACE", "BDA", "BAL", "CAR", "DRC", "MLC", "RCD", "FNC", "SEL", "LOG", "PUN", "JUB", "SNA", "SWS", "SML", "NPM", "ZAP", "RUS"],
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

# Build tag -> laws map (later profiles override earlier for specificity)
TAG_LAWS = {}
for profile, tags in PROFILE_TAGS.items():
    laws = P[profile]
    for tag in tags:
        TAG_LAWS[tag] = laws

# Explicit overrides for historical accuracy Jan 1 2000
OVERRIDES = {
    "SOV": P["russia_2000"],
    "USA": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "ENG": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "FRA": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_02", "freedom_trade_unions_02"),
    "GER": P["germany_style"],
    "HOL": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_02", "freedom_trade_unions_01"),
    "NOR": P["nordic"],
    "SWE": P["nordic"],
    "FIN": P["nordic"],
    "DEN": P["nordic"],
    "CHI": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_03"),
    "NKO": P["communist_hard"],
    "CUB": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_03"),
    "VIE": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_03"),
    "LAO": P["communist"],
    "PER": P["islamic_theocracy"],
    "SAU": P["islamic_theocracy"],
    "TAL": P["islamic_hard"],
    "AFG": ("censorship_03", "assembly_03", "freedom_religion_04", "lgbt_laws_04", "freedom_trade_unions_04"),
    "TUR": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_03", "freedom_trade_unions_02"),
    "ISR": P["israel_style"],
    "EGY": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "JPN": P["japan_style"],
    "KOR": P["asian_democracy"],
    "TAI": ("censorship_02", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "SIN": P["singapore_style"],
    "IND": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "RAJ": P["india_style"],
    "PAK": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "BRA": P["latin_america"],
    "MEX": P["latin_america"],
    "SAF": P["south_africa"],
    "HLS": P["hierocracy"],
    "BLR": P["post_soviet_auth"],
    "TRK": P["post_soviet_auth"],
    "UZB": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "YEM": ("censorship_02", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "IRQ": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "SYR": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "LBA": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "SUD": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_04"),
    "ZWE": ("censorship_03", "assembly_03", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_03"),
    "CHL": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "POL": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "HUN": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "ROM": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "BUL": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_04", "freedom_trade_unions_02"),
    "UKR": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "CHE": ("censorship_03", "assembly_03", "freedom_religion_04", "lgbt_laws_04", "freedom_trade_unions_04"),
    "TIB": P["china_tibet"],
    "ETK": P["china_tibet"],
    "BHU": P["bhutan_style"],
    "TIM": P["timor_style"],
    "PAL": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "LEB": P["lebanon_style"],
    "JOR": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "MOR": ("censorship_02", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "TUN": ("censorship_02", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "ALG": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "MMR": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "BRM": ("censorship_03", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "SIA": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_03", "freedom_trade_unions_02"),
    "MAY": ("censorship_02", "assembly_03", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_03"),
    "HKG": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "MAC": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "NEP": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "BAN": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "SRI": ("censorship_02", "assembly_02", "freedom_religion_03", "lgbt_laws_04", "freedom_trade_unions_02"),
    "PHI": ("censorship_02", "assembly_02", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "PTR": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
    "NLA": ("censorship_01", "assembly_01", "freedom_religion_02", "lgbt_laws_03", "freedom_trade_unions_02"),
}
TAG_LAWS.update(OVERRIDES)

DEFAULT_LAWS = P["african_democracy"]

LAW_SET_RE = re.compile(r"^\s*(" + "|".join(re.escape(x) for x in LAW_NAMES) + r")\s*$")


def extract_tag(filename: str) -> str:
    return filename.split(" - ")[0].strip()


def format_laws_block(laws: tuple[str, ...]) -> str:
    lines = ["\t\t#Freedom Laws"]
    for law in laws:
        lines.append(f"\t\t{law}")
    return "\n".join(lines) + "\n"


def strip_existing_laws(block_body: str) -> str:
    lines = block_body.splitlines(keepends=True)
    out = []
    skip_comment = False
    for line in lines:
        stripped = line.strip()
        if stripped == "#Freedom Laws":
            skip_comment = True
            continue
        if skip_comment and LAW_SET_RE.match(stripped):
            continue
        skip_comment = False
        out.append(line)
    return "".join(out)


def process_add_ideas_block(block_body: str, laws: tuple[str, ...]) -> str:
    body = strip_existing_laws(block_body)
    insertion = format_laws_block(laws)
    # Insert after opening brace line context: add at beginning of block content
    return insertion + body


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


def replace_add_ideas_blocks(section: str, laws: tuple[str, ...]) -> str:
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
        new_body = process_add_ideas_block(body, laws)
        result.append(header + new_body + closing)
        pos = brace_end
    return "".join(result)


def process_file(path: Path, laws: tuple[str, ...]) -> bool:
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

    new_block = replace_add_ideas_blocks(block, laws)
    if new_block == block:
        return False

    new_text = text[:block_open] + new_block + text[block_end:]
    path.write_text(new_text, encoding="utf-8", newline="\n")
    return True


def main() -> None:
    updated = 0
    skipped = []
    for path in sorted(COUNTRIES_DIR.glob("*.txt")):
        tag = extract_tag(path.name)
        laws = TAG_LAWS.get(tag, DEFAULT_LAWS)
        if process_file(path, laws):
            updated += 1
        elif "2000.1.1" in path.read_text(encoding="utf-8") and "add_ideas" in path.read_text(encoding="utf-8"):
            skipped.append(tag)

    print(f"Updated {updated} files")
    if skipped:
        print(f"Skipped (failed parse): {', '.join(skipped)}")


if __name__ == "__main__":
    main()
