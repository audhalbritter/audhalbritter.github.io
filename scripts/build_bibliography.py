#!/usr/bin/env python3
"""Build resources/works.bib from the papers listed in the April 2026 CV.

The CV decides which papers are included. Crossref supplies the bibliographic
record for each DOI. Data papers are tagged with the keyword datapaper.

The script also writes the publications page lists: full APA references grouped
by year, and the presentations taken from the CV.
"""

import html
import json
import re
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resources" / "works.bib"
MD = ROOT / "resources" / "_journal-articles.md"
APA_MD = ROOT / "resources" / "_publications-apa.md"
TALKS_MD = ROOT / "resources" / "_presentations.md"
CV_YAML = ROOT / "resources" / "cv-entries.yaml"
CACHE = ROOT / "scripts" / ".cache" / "crossref"

# Order follows the CV. datapaper marks the Scientific Data papers, which the
# publications page lists in their own section.
# doi, data paper, year as given in the CV
PAPERS = [
    ("10.1111/2041-210x.70338", False, "2026"),
    ("10.1038/s41559-025-02955-6", False, "2026"),
    ("10.1038/s41597-025-06503-6", True, "2026"),
    ("10.1111/jvs.70098", False, "2025"),
    ("10.1038/s41597-025-06045-x", True, "2025"),
    ("10.1111/2041-210X.70161", False, "2025"),
    ("10.1111/jvs.70061", False, "2025"),
    ("10.1038/s41597-025-05509-4", True, "2025"),
    ("10.1002/njb.04816", False, "2025"),
    ("10.1111/1365-2435.70056", False, "2025"),
    ("10.1111/ecog.07378", False, "2024"),
    ("10.1007/s00035-024-00317-9", False, "2024"),
    ("10.1038/s41597-024-02980-3", True, "2024"),
    ("10.1111/oik.10091", False, "2023"),
    ("10.1111/2041-210X.14160", False, "2023"),
    ("10.1038/s41597-023-02467-7", True, "2023"),
    ("10.1139/as-2020-0051", False, "2022"),
    ("10.1002/ecm.1555", False, "2023"),
    ("10.1371/journal.pone.0278339", False, "2022"),
    ("10.1038/s41597-022-01559-0", True, "2022"),
    ("10.1139/as-2020-0058", False, "2022"),
    ("10.1111/gcb.16060", False, "2022"),
    ("10.1088/1748-9326/abf464", False, "2021"),
    ("10.1016/j.ecoinf.2021.101232", False, "2021"),
    ("10.1038/s41559-021-01396-1", False, "2021"),
    ("10.1002/ece3.7026", False, "2021"),
    ("10.1002/ece3.7009", False, "2021"),
    ("10.1111/gcb.14854", False, "2020"),
    ("10.1038/s41559-020-1109-6", False, "2020"),
    ("10.1111/2041-210X.13331", False, "2020"),
    ("10.1111/gcb.15123", False, "2020"),
    ("10.1002/bes2.1680", False, "2020"),
    ("10.1038/s41597-020-0529-0", True, "2020"),
    ("10.1073/pnas.2003377117", False, "2020"),
    ("10.1016/j.ppees.2017.07.005", False, "2018"),
    ("10.1111/jeb.13262", False, "2018"),
    ("10.3389/fpls.2018.01548", False, "2018"),
    ("10.1073/pnas.1721285115", False, "2018"),
    ("10.3389/fpls.2018.01574", False, "2018"),
    ("10.1111/jeb.12701", False, "2015"),
    ("10.1111/geb.12066", False, "2013"),
    ("10.3852/11-071", False, "2012"),
]


def fetch_csl(doi: str) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = doi.replace("/", "_")
    cache_file = CACHE / f"{safe}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "audhalbritter-cv-builder/1.0 (mailto:me@audhalbritter.com)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode())
    message = payload["message"]
    cache_file.write_text(json.dumps(message))
    time.sleep(0.2)
    return message


def ascii_fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return "".join(ch for ch in text.lower() if ch.isalpha())


def bibtex_escape(text: str) -> str:
    text = html.unescape(text or "")
    text = text.replace("\xa0", " ").replace("\\", "")
    for ch in ("&", "%", "$", "#", "_"):
        text = text.replace(ch, "\\" + ch)
    return text.replace("{", "\\{").replace("}", "\\}")


def year_of(message: dict) -> str:
    # Prefer the print year so the citation matches the journal issue.
    for field_name in ("published-print", "issued", "published-online"):
        parts = (message.get(field_name) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            return str(parts[0][0])
    return ""


def authors_of(message: dict) -> list[dict]:
    people = []
    for person in message.get("author", []):
        if person.get("family"):
            people.append(person)
        elif person.get("name"):
            people.append({"family": person["name"], "given": ""})
    return people


def author_field(people: list[dict]) -> str:
    parts = []
    for person in people:
        family = bibtex_escape(person.get("family", "").strip())
        given = bibtex_escape(person.get("given", "").strip())
        if given:
            parts.append(f"{family}, {given}")
        else:
            parts.append("{" + family + "}")
    return " and ".join(parts)


def first_title_word(title: str) -> str:
    for word in title.split():
        folded = ascii_fold(word)
        if len(folded) > 3 and folded not in {"with", "from", "that", "this", "across"}:
            return folded[:12]
    return "paper"


def entry_key(people: list[dict], year: str, title: str, used: set[str]) -> str:
    family = ascii_fold(people[0]["family"]) if people else "unknown"
    base = f"{family}{year}"
    key = base
    if key in used:
        key = f"{base}{first_title_word(title)}"
    n = 2
    candidate = key
    while candidate in used:
        candidate = f"{key}{n}"
        n += 1
    used.add(candidate)
    return candidate


def field(name: str, value: str) -> str:
    if not value:
        return ""
    return f"  {name} = {{{value}}},\n"


def container_of(message: dict) -> str:
    container = message.get("container-title") or message.get("short-container-title") or [""]
    if isinstance(container, list):
        container = container[0] if container else ""
    return clean_markup(container)


def clean_markup(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<\s*i\s*>", "*", text, flags=re.I)
    text = re.sub(r"<\s*/\s*i\s*>", "*", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


# Kept in their published capitalisation. Curly braces stop APA sentence case
# from lowercasing proper nouns and the name of the R language.
PROTECTED_PHRASES = (
    "British Ecological Society",
    "Northern Hemisphere",
    "High Arctic",
    "Maloti-Drakensberg",
    "South Africa",
    "Afromontane",
    "Tree of Life",
    "COVID‐19",
    "COVID-19",
    "Gongga",
    "Svalbard",
    "Finse",
    "Norway",
    "China",
    "Perú",
    "Puna",
    "Korell",
    "Arctic and alpine",
    "Sentinel-2A",
)

BINOMIALS = (
    "Vaccinium myrtillus",
    "Brachypodium sylvaticum",
    "Ranunculus acris",
)


def cite_title(raw: str) -> str:
    """BibTeX title with italics and case protection for APA sentence case."""
    text = html.unescape(raw or "")
    for name in BINOMIALS:
        text = re.sub(
            rf"<\s*i\s*>\s*{re.escape(name)}\s*<\s*/\s*i\s*>",
            name,
            text,
            flags=re.I,
        )
        text = re.sub(
            rf"{re.escape(name)}( L\.?)?",
            lambda match, binomial=name: (
                f"@@IT@@{binomial}@@END@@" + (" @@L@@" if match.group(1) else "")
            ),
            text,
        )
    pieces = re.split(r"(@@IT@@.*?@@END@@)", text)
    out = []
    for piece in pieces:
        if piece.startswith("@@IT@@"):
            inner = bibtex_escape(piece.removeprefix("@@IT@@").removesuffix("@@END@@"))
            out.append("{\\textit{" + inner + "}}")
            continue
        plain = re.sub(r"<[^>]+>", "", piece)
        plain = bibtex_escape(plain)
        for phrase in sorted(PROTECTED_PHRASES, key=len, reverse=True):
            escaped = bibtex_escape(phrase)
            plain = plain.replace(escaped, "{" + escaped + "}")
        plain = plain.replace("@@L@@", "{L}")
        plain = re.sub(r"(?<![{}\\\w])R(?![\w])", "{R}", plain)
        out.append(plain)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def to_bibtex(key: str, message: dict, datapaper: bool, year: str) -> str:
    people = authors_of(message)
    title = cite_title(" ".join(message.get("title", [""])))
    container = container_of(message)
    volume = str(message.get("volume", "") or "")
    # Some journals put a calendar year in the volume field. Drop it when
    # that year is not the citation year.
    volume_is_other_year = volume.isdigit() and len(volume) == 4 and volume != year
    lines = [f"@article{{{key},"]
    lines.append(field("author", author_field(people)))
    lines.append(field("title", title))
    lines.append(field("journal", bibtex_escape(container)))
    lines.append(field("year", year))
    if not volume_is_other_year:
        lines.append(field("volume", bibtex_escape(volume)))
        lines.append(field("number", bibtex_escape(str(message.get("issue", "") or ""))))
    lines.append(field("pages", bibtex_escape(str(message.get("page", "") or ""))))
    doi = message.get("DOI", "")
    lines.append(field("doi", doi))
    if doi:
        lines.append(field("url", f"https://doi.org/{doi}"))
    if datapaper:
        lines.append(field("keywords", "datapaper"))
        lines.append(field("note", "Data paper"))
    lines.append("}\n")
    return "".join(line for line in lines if line != "")


def markdown_authors(people: list[dict]) -> str:
    def label(person: dict) -> str:
        family = clean_markup(person.get("family", ""))
        given = clean_markup(person.get("given", ""))
        initials = "".join(part[0] for part in given.replace("-", " ").split() if part)
        name = f"{family} {initials}".strip()
        if family.lower() == "halbritter":
            name = f"**{name}**"
        return name

    if len(people) <= 12:
        return ", ".join(label(person) for person in people)
    parts = [label(person) for person in people[:6]]
    focal = next(
        (i for i, person in enumerate(people) if person.get("family", "").lower() == "halbritter"),
        None,
    )
    if focal is not None and focal >= 6:
        parts.append("… " + label(people[focal]))
    parts.append("et al.")
    return ", ".join(parts)


def to_markdown(message: dict, year: str, datapaper: bool) -> str:
    people = authors_of(message)
    title = clean_markup(" ".join(message.get("title", [""])))
    journal = container_of(message)
    volume = str(message.get("volume", "") or "")
    number = str(message.get("issue", "") or "")
    pages = str(message.get("page", "") or "").replace("--", "–")
    doi = message.get("DOI", "")
    journal_bit = f"*{journal}*"
    # Some journals use the calendar year as the volume. Skip that when it
    # is not the citation year, so the entry does not look like two years.
    volume_is_other_year = volume.isdigit() and len(volume) == 4 and volume != year
    if volume and not volume_is_other_year:
        journal_bit += f" {volume}"
        if number:
            journal_bit += f"({number})"
    elif number and volume_is_other_year:
        journal_bit += f", issue {number}"
    if pages:
        journal_bit += f", {pages}"
    bits = [
        f"{markdown_authors(people)} ({year}).",
        f"{title}.",
        f"{journal_bit}.",
    ]
    if doi:
        bits.append(f"[{doi}](https://doi.org/{doi})")
    if datapaper:
        bits.append("Data paper.")
    return "- " + " ".join(bits)


def bold_halbritter(fragment: str) -> str:
    """Bold the APA form of Aud's name wherever the full author list prints it."""
    return re.sub(
        r"Halbritter,\s+[A-Z]\.(?:\s+[A-Z]\.)*",
        lambda match: f"<strong>{match.group(0)}</strong>",
        fragment,
    )


def apa_entries() -> dict[str, str]:
    """Render every work in APA with the full author list.

    Stock APA stops at 20 names. The publications page needs every author,
    so this uses the same style with that cutoff removed.
    """
    source = (ROOT / "resources" / "apa.csl").read_text(encoding="utf-8")
    source = source.replace(
        'et-al-min="21" et-al-use-first="19" et-al-use-last="true"',
        'et-al-min="500" et-al-use-first="500"',
    )
    csl = CACHE / "apa-full.csl"
    csl.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            "pandoc",
            "--citeproc",
            f"--csl={csl}",
            f"--bibliography={OUT}",
            "-t",
            "html",
            "-f",
            "markdown",
        ],
        input="---\nnocite: '@*'\n---\n\n",
        text=True,
        capture_output=True,
        check=True,
    )
    rendered: dict[str, str] = {}
    parts = re.split(r'<div id="ref-([^"]+)" class="csl-entry"[^>]*>', result.stdout)
    for key, chunk in zip(parts[1::2], parts[2::2]):
        body = bold_halbritter(chunk.split("</div>", 1)[0].strip())
        author_list = body.split("(20", 1)[0]
        if "et al" in author_list or "…" in author_list:
            raise SystemExit(f"{key} still truncates the author list")
        rendered[key] = body
    return rendered


def year_blocks(records: list[dict], rendered: dict[str, str], datapaper: bool) -> str:
    chosen = [record for record in records if record["datapaper"] is datapaper]
    years: dict[str, list[str]] = {}
    for record in chosen:
        years.setdefault(record["year"], []).append(record["key"])
    parts = []
    for year in sorted(years, reverse=True):
        entries = "\n".join(
            f'<div id="ref-{key}" class="csl-entry">\n{rendered[key]}\n</div>'
            for key in years[year]
        )
        parts.append(f"### {year}\n\n<div class=\"hanging-indent\">\n{entries}\n</div>\n")
    return "\n".join(parts)


def write_apa_page(records: list[dict]) -> None:
    rendered = apa_entries()
    missing = [record["key"] for record in records if record["key"] not in rendered]
    if missing:
        raise SystemExit(f"APA render missed {', '.join(missing)}")
    body = (
        year_blocks(records, rendered, datapaper=False)
        + "\n## Data papers\n\n"
        + "These *Scientific Data* papers are included in the 42 papers above.\n\n"
        + year_blocks(records, rendered, datapaper=True)
    )
    APA_MD.write_text(body.strip() + "\n", encoding="utf-8")
    print(f"Wrote {APA_MD}")


def yaml_items(section: str) -> list[dict[str, str]]:
    """Read one list from the CV yaml. Values in that file are single-line."""
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    started = False
    for line in CV_YAML.read_text(encoding="utf-8").splitlines():
        if not started:
            if line == f"{section}:":
                started = True
            continue
        if line and not line.startswith(" "):
            break
        if line.startswith("  - "):
            if current:
                items.append(current)
            current = {}
            payload = line[4:]
        elif line.startswith("    ") and current:
            payload = line.strip()
        else:
            continue
        key, _, value = payload.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        current[key.strip()] = value
    if current:
        items.append(current)
    return items


def write_presentations() -> None:
    parts = []
    by_year: dict[str, list[dict[str, str]]] = {}
    for talk in yaml_items("talks"):
        by_year.setdefault(talk.get("dates", ""), []).append(talk)
    for year, talks in by_year.items():
        lines = [f"### {year}\n"]
        for talk in talks:
            title = talk.get("title", "").replace("Ranunculus acris", "*Ranunculus acris*")
            detail = ", ".join(
                piece for piece in (talk.get("organization", ""), talk.get("location", "")) if piece
            )
            ending = "" if title.endswith((".", "?", "!")) else "."
            lines.append(f"- **{title}**{ending} {detail}.")
        parts.append("\n".join(lines))
    TALKS_MD.write_text("\n\n".join(parts).strip() + "\n", encoding="utf-8")
    print(f"Wrote {TALKS_MD}")


def main() -> None:
    used = set()
    blocks = []
    by_year: dict[str, list[str]] = {}
    records = []
    failed = []
    for doi, datapaper, year in PAPERS:
        try:
            message = fetch_csl(doi)
        except Exception as exc:
            failed.append((doi, str(exc)))
            print("FAIL", doi, exc)
            continue
        people = authors_of(message)
        title = clean_markup(" ".join(message.get("title", [""])))
        key = entry_key(people, year, title, used)
        blocks.append(to_bibtex(key, message, datapaper, year))
        by_year.setdefault(year, []).append(to_markdown(message, year, datapaper))
        records.append({"key": key, "year": year, "datapaper": datapaper})
        print("OK", key)
    header = (
        "% Generated by scripts/build_bibliography.py from the April 2026 CV.\n"
        "% Edit this file to correct a record, then re-render the site.\n\n"
    )
    OUT.write_text(header + "\n".join(blocks), encoding="utf-8")
    md_parts = []
    for year in sorted(by_year, reverse=True):
        md_parts.append(f"### {year}\n")
        md_parts.append("\n".join(by_year[year]))
        md_parts.append("")
    MD.write_text("\n".join(md_parts).strip() + "\n", encoding="utf-8")
    print(f"Wrote {len(blocks)} entries to {OUT}")
    print(f"Wrote {MD}")
    if failed:
        raise SystemExit(f"{len(failed)} DOIs failed")
    write_apa_page(records)
    write_presentations()


if __name__ == "__main__":
    main()
