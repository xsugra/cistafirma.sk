#!/usr/bin/env python3
"""Audit ciest v backtickoch -- to, co `check_markdown_links.py` nevidí.

`check_markdown_links.py` kontroluje odkazy `[text](cesta)`. Lenže väčšina
dokumentácie v tomto repe neodkazuje odkazom, ale **citáciou dôkazu**:

    `backend/registers/models.py:705-710`
    `docs/archive/FIRMY_SZCO_QUICK_START.md:93-94`

To je iný zápis a iná trieda chyby: odkaz prejde auditom, lebo kotva aj cesta
sedia, kým citácia v backtickoch sa pri presune súboru ticho rozpadne. Presne to
sa stalo pri konsolidácii, ktorá presunula 19 dokumentov do `docs/archive/`:
markdownové odkazy sa prepísali, 19 citácií v backtickoch ostalo ukazovať do
koreňa repa, a audit napriek tomu hlásil OK. (Aj preto je to samostatný skript
a nie ďalšia funkcia v tom druhom.)

Kontrolujú sa dve pravidlá. Obe boli zmerané na celom repe pred tým, než sa
sem pridali, a obe mali nula falošných poplachov:

**A. Cesta s koreňom repa.** Citácia obsahuje `/` a jej prvý segment je
skutočný podadresár koreňa (`backend/`, `docs/`, `frontend/`, ...). Taká cesta
je jednoznačná -- niet čo hádať -- takže sa dá overiť, či súbor existuje a či
citovaný riadok nie je za koncom súboru.

Zvyšok sa zámerne preskakuje. `registers/models.py` znamená
`backend/registers/models.py` a `lib/apiClient.ts` znamená
`frontend/lib/apiClient.ts`; kto prvý segment nevie dosadiť, nemá hádať. Skúšal
som to širšie -- každú cestu s `/` brať ako koreňovú -- a na 503 kontrol to
vyrobilo **112 falošných nálezov**. Brána, ktorá kričí 112-krát, sa vypne, a to
je horšie než brána, ktorá túto jednu triedu nevidí.

**B. Holé meno, ktoré žije už len v archíve.** Citácia je `MENO.md` bez `/`
a súbor s tým menom existuje **výhradne** v `docs/archive/`. Potom z koreňa
repa nič nerozbalí. Keď to isté meno existuje aj na živej ceste (`README.md`),
preskakuje sa -- tam holé meno rozumie niečomu, čo tento skript nevie určiť.
Riadok, ktorý slovo „archív" obsahuje, sa tiež preskakuje: pomenovať
archivovaný dokument je v poriadku, citovať ho ako živý nie.

**Dokumenty vnútri `docs/archive/` sa pravidlom B nekontrolujú** -- a to je
podmienka, bez ktorej pravidlo nefunguje. `docs/archive/README.md` vymenúva
archivované dokumenty holými menami a archivované dokumenty sa navzájom
odkazujú rovnako; tam holé meno **správne** mierni na súrodenca v tom istom
adresári, takže nič nie je rozbité. Prvá verzia tohto skriptu archív
nekontrolovala len v mojom meraní a nie v kóde, a hneď vyrobila **64 nálezov,
z toho 63 v archíve** -- čiže tú istú chybu, pred ktorou varuje odsek o 112
falošných poplachoch vyššie. Pravidlo A archív kontroluje ďalej: koreňová cesta
je jednoznačná všade.

Čo skript **nevie** a nemá predstierať: cestu k adresáru (regex chce príponu),
a to, či citovaný riadok naozaj nesie to, čo mu text pripisuje. To druhé
zostáva na čítanie -- skript hľadá rozbité cesty, nie nesprávne tvrdenia.

A jedna vec sa ukázala hneď pri prvom zapojení do `make docs-audit`:
**ukážka citácie vyzerá presne ako citácia.** `scripts/README.md` tvar
ukazoval na `docs/archive/FOO.md:22` -- vymyslené meno, aby bolo vidieť, o čom
pravidlo je -- a skript ho ohlásil. Mal pravdu: taký súbor naozaj neexistuje
a skript nemá ako rozoznať ukážku od odkazu. To nie je chyba, ktorú by mal
riešiť heuristikou („toto vyzerá ako príklad"); je to vlastnosť dizajnu.
Príklad preto buď cituje cestu, ktorá existuje, alebo používa zástupný tvar
(`docs/archive/<MENO>.md`), ktorý regex nechytí -- presne tak, ako to teraz
robí ten README.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".venv",
    "build",
    "dist",
    "node_modules",
    "venv",
    "__pycache__",
}

# Prípony, pri ktorých má zmysel hovoriť o ceste k súboru. `.md` je tu preto, že
# práve citácie na dokumenty sa pri konsolidácii rozpadli.
EXTS = "py|ts|tsx|js|jsx|sh|yml|yaml|json|toml|cfg|md|css|html"

CITATION_RE = re.compile(
    rf"`(?P<path>[A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:{EXTS}))"
    rf"(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?`"
)

BARE_MD_RE = re.compile(r"`(?P<name>[A-Za-z0-9_][A-Za-z0-9_.-]*\.md)"
                        r"(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?`")

ARCHIVE_WORD_RE = re.compile(r"archiv", re.IGNORECASE)


def iter_markdown_files(root: Path):
    for path in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        yield path


def top_level_dirs(root: Path) -> Set[str]:
    """Skutočné podadresáre koreňa -- podľa nich sa pozná koreňová cesta.

    Počíta sa to za behu, nie z konštanty: zoznam v kóde by zaostal za repoom
    a ticho by prestal kontrolovať nový adresár.
    """
    return {
        p.name
        for p in root.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS
    }


def archive_only_names(root: Path) -> Tuple[Set[str], Set[str]]:
    """(mená žijúce výhradne v docs/archive, mená žijúce aj inde)."""
    only_archive: Set[str] = set()
    live: Set[str] = set()
    for path in root.rglob("*.md"):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if rel.parts[:2] == ("docs", "archive"):
            only_archive.add(path.name)
        else:
            live.add(path.name)
    return only_archive - live, live


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def main() -> int:
    root = REPO_ROOT
    roots = top_level_dirs(root)
    archived_only, _ = archive_only_names(root)

    problems: List[str] = []
    checked = 0
    seen = set()

    for md in iter_markdown_files(root):
        rel_parts = md.relative_to(root).parts
        rel_doc = str(md.relative_to(root))
        # V archíve holé meno mieri na súrodenca -- pozri docstring, pravidlo B.
        in_archive = rel_parts[:2] == ("docs", "archive")
        for lineno, line in enumerate(
            md.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            # -- A: koreňová cesta -------------------------------------------
            for m in CITATION_RE.finditer(line):
                ref = m.group("path")
                if "/" not in ref or ref.split("/", 1)[0] not in roots:
                    continue
                key = ("A", rel_doc, lineno, ref, m.group("start"), m.group("end"))
                if key in seen:
                    continue
                seen.add(key)
                checked += 1

                target = root / ref
                if not target.is_file():
                    problems.append(
                        f"{rel_doc}:{lineno}: `{ref}` -- taký súbor neexistuje"
                    )
                    continue
                if m.group("start"):
                    cited = int(m.group("end") or m.group("start"))
                    total = line_count(target)
                    if cited > total:
                        problems.append(
                            f"{rel_doc}:{lineno}: `{ref}:{cited}` -- "
                            f"súbor má len {total} riadkov"
                        )

            # -- B: holé meno, ktoré žije už len v archíve -------------------
            if in_archive or ARCHIVE_WORD_RE.search(line):
                continue
            for m in BARE_MD_RE.finditer(line):
                name = m.group("name")
                if name not in archived_only:
                    continue
                key = ("B", rel_doc, lineno, name, m.group("start"), m.group("end"))
                if key in seen:
                    continue
                seen.add(key)
                checked += 1
                cited = (
                    f"{name}:{m.group('start')}" if m.group("start") else name
                )
                problems.append(
                    f"{rel_doc}:{lineno}: `{cited}` -- existuje len ako "
                    f"`docs/archive/{name}`, z koreňa repa nič nerozbalí"
                )

    if problems:
        print("Audit citácií v backtickoch: NÁLEZY")
        for p in problems:
            print(f"  {p}")
        print(f"\nSkontrolovaných citácií: {checked}, nálezov: {len(problems)}")
        return 1

    print(
        f"Audit citácií v backtickoch OK. "
        f"Skontrolovaných citácií: {checked}, nálezov: 0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
