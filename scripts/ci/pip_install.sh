#!/usr/bin/env bash
#
# Inštalácia backend závislostí pre CI, s opakovaním celého kroku.
#
# PREČO TO EXISTUJE
# -----------------
# `pip` sa už raz opakuje sám: `--retries 3 --timeout 120` pribudlo 7. 5. 2026
# (e9be132) presne ako mitigácia tohto problému. Nestačilo to. 19. 9. 2026
# zomrel `backend_tests` v pipeline 193 (build 1360) na
#
#     pip._vendor.urllib3.exceptions.ReadTimeoutError:
#     HTTPSConnectionPool(host='files.pythonhosted.org', port=443): Read timed out.
#
# po troch vlastných pokusoch pipu. `grep -c "Ran .* tests"` v trace = 0, teda
# job zlyhal **pred prvým testom** a jeho červená nenesie o kóde nič. Presne
# to je trieda zlyhania, ktorú má tento skript odstrániť: sieť je efemérna,
# kód nie.
#
# `--retries` opakuje *spojenie*. Toto opakuje *krok* — znovu spustí pip, teda
# aj rozlíšenie mena, aj celý prenos. Pre DNS výpadok (ktorý tento projekt už
# raz zažil, viď `registers_syncprogress` riadok 2) je to jediná účinná vec.
#
# ČO ZÁMERNE NEROBÍ
# -----------------
# Neopakuje **job** ako celok (`retry: when: script_failure` v `.gitlab-ci.yml`).
# Tým by sa opakovali aj testy — a červená pipeline by prestala znamenať
# „test neprešiel". Opakovanie patrí sieťovému kroku, nie kontrolnému.
#
# PREČO SKRIPT A NIE `|` BLOK V YAMLI
# -----------------------------------
# Dá sa testovať lokálne (viď `--selftest` nižšie) a je na jednom mieste pre
# oba joby, ktoré ho volajú (`backend_validate`, `backend_tests`). YAML blok
# by sa musel duplikovať, alebo použiť `!reference` — a rozbiť celý
# `.gitlab-ci.yml` je drahšie než duplikovať.
#
# PREČO NIE `exit 0` V TELE SLUČKY
# --------------------------------
# GitLab Runner zliepa `before_script` a `script` do jedného shell skriptu.
# `exit 0` v `before_script` by teda ukončil **celý job ako úspešný** a testy
# by sa nikdy nespustili — zelená pipeline bez testov. Preto `break` a kontrola
# až za slučkou.
#
# PREČO JE CESTA ODVODENÁ OD SKRIPTU (a nie `/backend/...` ani `backend/...`)
# -------------------------------------------------------------------------
# Prvá verzia tohto skriptu mala `pozadovane="/backend/requirements.txt"` —
# absolútnu cestu. Runner ale klonuje do `/builds/<skupina>/<projekt>` a spúšťa
# job v **koreni repa**, takže `/backend/` tam neexistuje. Pipeline 194 (build
# 1362) preto zlyhala takto:
#
#     ERROR: Could not open requirements file: [Errno 2]
#     No such file or directory: '/backend/requirements.txt'
#
# Opakovanie pritom fungovalo presne ako malo (20 s, 40 s) — červená bola len
# a výhradne z cesty. Relatívna cesta `backend/requirements.txt` by v CI vyšla,
# ale rozbila by sa v každom jobe, ktorý si predtým spraví `cd` (napr.
# `backend_tests` má `cd backend` v `script`, a ten istý `before_script` sa
# spúšťa pre oba joby). Preto sa cesta skladá z umiestnenia skriptu: je
# správna z ľubovoľného cwd.
#
# Poučenie, ktoré stojí za zapísanie: `--selftest` stubuje `pip`, takže sa
# pôvodne cesty **vôbec nedotkol** a prepustil práve tú chybu, na ktorej
# záležalo. Kontrola existencie nižšie preto beží aj v `--selftest` — self-test
# musí preveriť aj argumenty, nielen návratové kódy.

set -uo pipefail

POKUSOV="${CI_PIP_INSTALL_ATTEMPTS:-3}"
Cakanie="${CI_PIP_INSTALL_RETRY_DELAY:-20}"

# Cesta k repu odvodená z umiestnenia skriptu (`scripts/ci/` → o dve vyššie),
# aby bola správna bez ohľadu na to, odkiaľ sa skript volá.
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
pozadovane="${CI_PIP_REQUIREMENTS:-$repo_root/backend/requirements.txt}"

log() { printf '%s\n' "$*" >&2; }

# `--selftest` overí samotnú logiku opakovania bez toho, aby sa čokoľvek
# inštalovalo: `pip` sa nahradí funkciou, ktorá zlyhá presne toľkokrát, koľko
# povie `--selftest <n>`. Bez tohto by sa skript, ktorý sa v CI používa raz za
# časť, nikdy netestoval — a je to práve skript, ktorý rozhoduje o tom, či sa
# testy vôbec spustia.
if [ "${1:-}" = "--selftest" ]; then
    zlyhani="${2:?--selftest potrebuje počet zlyhaní}"
    Cakanie=0
    volani=0
    pip() {
        volani=$((volani + 1))
        [ "$volani" -le "$zlyhani" ] && return 1
        return 0
    }
fi

# Beží v OBoch režimoch, vrátane `--selftest`: práve preto, že stubovaný `pip`
# by zlú cestu ticho prehliadol. Toto je kontrola, ktorá by odhalila pipeline
# 194 ešte na mojom stroji.
log "Závislosti: $pozadovane"
if [ ! -f "$pozadovane" ]; then
    log "CHYBA: $pozadovane neexistuje — niet čo inštalovať."
    exit 1
fi

pokus=1
while true; do
    # `set -o pipefail` je nastavené, ale `pip` tu nie je v pipe; návratový
    # kód je jeho vlastný.
    if pip install --no-cache-dir --retries 3 --timeout 120 -r "$pozadovane"; then
        log "Závislosti nainštalované (pokus $pokus)."
        break
    fi

    if [ "$pokus" -ge "$POKUSOV" ]; then
        log "pip install zlyhal v $pokus pokusoch; vzdávam to."
        exit 1
    fi

    cakaj=$((pokus * Cakanie))
    log "pip install (pokus $pokus) zlyhal; opakujem o ${cakaj}s."
    [ "$cakaj" -gt 0 ] && sleep "$cakaj"
    pokus=$((pokus + 1))
done

if [ "${1:-}" = "--selftest" ]; then
    log "SELFTEST volani=$volani (ocakavane $((zlyhani + 1)))"
fi
