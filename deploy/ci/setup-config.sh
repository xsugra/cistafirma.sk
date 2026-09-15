#!/bin/bash
# ============================================================================
#  Vygeneruje /home/sam/gitlab-runner/config/config.toml
# ============================================================================
#
#  Tento skript je jediný zdroj pravdy pre konfiguráciu runnera.
#  config.toml je výstup — needituj ho ručne, zmeň tento skript a spusť ho.
#
#  Token sa neberie odtiaľto; číta sa zo súboru, ktorý vytvorí:
#     docker exec gitlab-server gitlab-rails runner \
#       'print Ci::Runner.find(1).token' > runner-token.txt
#
#  Spustenie:   bash /home/sam/gitlab-runner/setup-config.sh
#  Potom:       cd /home/sam/gitlab-runner && docker compose restart gitlab-runner
# ============================================================================

set -euo pipefail

RUNDIR=/home/sam/gitlab-runner
TOKENFILE=${TOKENFILE:-/home/sam/gitlab-runner-setup/runner-token.txt}
CONF="$RUNDIR/config/config.toml"
GITLAB_URL="http://gitlab.home.arpa:8088"
GITLAB_IP="100.120.104.84"
RUNNER_NAME="sam-lenovo"

[ -f "$TOKENFILE" ] || { echo "chýba $TOKENFILE" >&2; exit 1; }
TOKEN=$(tr -d '\r\n' < "$TOKENFILE")
[ -n "$TOKEN" ] || { echo "token je prázdny" >&2; exit 1; }

mkdir -p "$RUNDIR/config"
[ -f "$CONF" ] && cp -a "$CONF" "$CONF.bak-$(date +%Y%m%d-%H%M%S)"

cat > "$CONF" <<'EOF'
# ==========================================================================
#  GitLab Runner na sam-lenovo — BEZPEČNÝ PROFIL cez socket proxy
#  Generuje setup-config.sh. Neupravuj ručne, radšej zmeň ten skript.
# ==========================================================================

# Len jeden job naraz. Stroj má 3.7 GiB RAM a beží na ňom GitLab,
# motionEye aj kamera. Dva paralelné joby = swap thrashing.
concurrent = 1
check_interval = 3
log_level = "info"

[[runners]]
  name = "__RUNNER_NAME__"
  url = "__GITLAB_URL__"
  token = "__TOKEN__"
  executor = "docker"
  limit = 1

  # ----------------------------------------------------------------------
  # ----------------------------------------------------------------------
  # run_untagged sa TU NASTAVIT NEDA — a to je neintuitívne.
  #
  # V gitlab-runneri 19.x je tento kľúč v config.toml pre UŽ REGISTROVANÝ
  # runner INERTNÝ: runner ho posiela len pri registrácii, pri spustení
  # (run) ho GitLab ignoruje. Overené 15. 9. 2026 — po reštarte s touto
  # hodnotou nastavenou na true ostal v GitLabe stav false
  # (ci_runners.updated_at sa nepohol).
  #
  # Skutočné nastavenie je SERVER-SIDE, v tabuľke ci_runners. Zapína sa:
  #
  #   docker exec gitlab-server gitlab-rails runner
  #     'Ci::Runner.find(1).update!(run_untagged: true)'
  #
  # Bez neho runner nespustí ANI JEDEN job, lebo .gitlab-ci.yml nemá žiadne
  # "tags:" — presne to sa stalo 11. 9. 2026 a 4 dni to nikto nevidel.
  # ----------------------------------------------------------------------
  # ----------------------------------------------------------------------

  # Runner inak varuje, že s request_concurrency=1 sa joby pri long pollingu
  # zdržia. Toto sa týka len čakania na job, nie počtu bežiacich buildov —
  # tie stále drží concurrent=1 a limit=1.
  request_concurrency = 2

  [runners.docker]
    # ----------------------------------------------------------------------
    # KLUCOVE: runner sa NEROZPRAVA so socketom, ale s obmedzenym proxym.
    # Proxy bezi v sieti runner-net a nema publikovany ziadny port, takze
    # je dosiahnutelny len z tohto kontajnera.
    # ----------------------------------------------------------------------
    host = "tcp://docker-socket-proxy:2375"
    tls_verify = false

    image = "alpine:latest"

    # ----------------------------------------------------------------------
    # BEZPECNOST — toto je to, co skutocne zatvara hrozbu z runbooku.
    # Proxy sam o sebe nestaci (nevidi do tela poziadavky), takze:
    #   1) job kontajner NIE JE privilegovany
    #   2) job kontajner NEDOSTAVA docker.sock
    # Keby tu raz niekto pridal "/var/run/docker.sock:/var/run/docker.sock",
    # alebo nastavil privileged = true, cely profil pada.
    # ----------------------------------------------------------------------
    privileged = false
    volumes = ["/cache"]

    # Kontajnery dostavaju DNS z routera (192.168.1.1), ktory o home.arpa
    # nevie -> staticky zaznam. Overene: git ls-remote z kontajnera funguje.
    extra_hosts = ["gitlab.home.arpa:__GITLAB_IP__"]
    network_mode = "bridge"

    # Registry je ciste HTTP (gitlab.home.arpa:8088), takze TLS verify off.
    # Netahat image odznova pri kazdom jobe.
    pull_policy = ["if-not-present"]
    disable_cache = false
    shm_size = 0

    # Strop na pamat: ked job potrebuje viac, dostane OOM kill (job zlyha),
    # ale stroj prezije. memory_swap = memory => job nesmie swapovat.
    memory = "1g"
    memory_swap = "1g"
    oom_kill_disable = false

    # Biela listina obrazov — presne to, co CI potrebuje, nic viac.
    # docker:27.1.2 a docker:27.1.2-dind tu ZAMERNE NIE SU: build joby
    # potrebuju DinD, DinD potrebuje privileged, a to by zrusilo cely
    # bezpecnostny profil. Build joby preto patria na iny stroj.
    #
    # kubectl tu uz NIE JE. Stage `build` aj `deploy` boli 15. 9. 2026
    # odstranene (viď docs/DEVOPS_CICD.md), takze ziaden job kubectl
    # nepouziva. Biela listina, ktora drzi obraz pre job, ktory neexistuje,
    # len predstiera, ze nieco chrani.
    #
    # Postgres a Redis su SERVICE kontajnery jobu `backend_tests`. Testy
    # backendu MUSIA bežať na Postgrese: migracia companies/0014 vytvara
    # index s `text_pattern_ops`, co je Postgres-only trieda operatorov,
    # takze na SQLite spadne `create_test_db` este pred prvym testom. Bez
    # Redisu zase padne sest testov (pat v hladani osob, jeden admin
    # dashboard) a healthz test caka 200, ale dostane 503.
    # Verzie su tie, ktore prevadzkuje produkcia (docker-compose.yml).
    allowed_images = [
      "python:3.12-slim",
      "node:20-alpine",
      "alpine/helm:3.17.2",
      "postgres:16-alpine",
      "redis:7-alpine",
      "alpine:latest"
    ]
EOF

# Placeholdery sa dosadzujú až tu, nad hotovým súborom. Vďaka tomu môže
# komentár v tele heredocy obsahovať $, apostrofy či backslashe bez toho,
# aby ich shell interpretoval (raz sa to stalo a config.toml mal diery).
sed -i \
  -e "s|__RUNNER_NAME__|$RUNNER_NAME|g" \
  -e "s|__GITLAB_URL__|$GITLAB_URL|g" \
  -e "s|__GITLAB_IP__|$GITLAB_IP|g" \
  -e "s|__TOKEN__|$TOKEN|g" \
  "$CONF"

# Hlasná kontrola: nevyplnený placeholder znamená rozbitý config, nie tichý.
if grep -q '__[A-Z_]*__' "$CONF"; then
  echo "CHYBA: v config.toml ostal nevyplnený placeholder:" >&2
  grep -o '__[A-Z_]*__' "$CONF" | sort -u >&2
  exit 1
fi

chmod 600 "$CONF"
echo "zapísané: $CONF ($(stat -c '%U:%G %a %s B' "$CONF"))"
