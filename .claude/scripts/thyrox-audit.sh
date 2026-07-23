#!/bin/bash
# =============================================================================
# .claude/scripts/thyrox-audit.sh — auditoría mecánica de coherencia (kaupamex)
# =============================================================================
# Corre los gates verificables del monorepo kaupamex y emite un score por
# chequeo. NO corrige — documenta. El juicio cualitativo lo añade el agente
# increment-acceptor vía /thyrox:audit-coherence.
#
# Adaptado del thyrox-audit.sh de NestorMonroy/thyrox (Command -> Script +
# Agente), repunteado a la realidad de kaupamex: estado en el SMD (no
# ROADMAP/.thyrox/), skill `thyrox` (no pm-thyrox), 5 submódulos como clones
# hermanos, y lenguaje-muerto = los tokens que kaupamex ya prohibió.
#
# Uso:
#   bash .claude/scripts/thyrox-audit.sh            # reporte a stdout
#   bash .claude/scripts/thyrox-audit.sh --strict   # exit 1 si algún FAIL
# =============================================================================
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; cd "$ROOT"
PARENT="$(dirname "$ROOT")"
STRICT=false; FAST=false
for a in "$@"; do
  [[ "$a" == "--strict" ]] && STRICT=true
  [[ "$a" == "--fast" ]]   && FAST=true   # omite el gate de referencias (lento) — para hooks
done
PASS=0; FAIL=0; WARN=0
ok()   { echo "PASS  · $1"; PASS=$((PASS+1)); }
bad()  { echo "FAIL  · $1"; FAIL=$((FAIL+1)); }
warn() { echo "WARN  · $1"; WARN=$((WARN+1)); }

echo "# Auditoría de coherencia kaupamex — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Repo: $ROOT"
echo ""

CANON=".claude/CLAUDE.md .claude/skills/thyrox/SKILL.md"
CANON_DIRS=".claude/commands .claude/rules .claude/agents .claude/skills/thyrox/references"

# --- 1. Referencias (markdown links rotos) ---
if $FAST; then
    echo "SKIP  · Referencias: omitido en modo --fast"
elif [[ -f .claude/scripts/validate-broken-references.py ]]; then
    if python3 .claude/scripts/validate-broken-references.py --links-only >/dev/null 2>&1; then
        ok "Referencias: 0 broken markdown links (--links-only)"
    else
        bad "Referencias: hay broken markdown links — corre validate-broken-references.py"
    fi
    rm -f reference-validation-report.txt 2>/dev/null
else
    warn "Referencias: validate-broken-references.py no encontrado"
fi

# --- 2a. Lenguaje muerto DURO: tokens de template nunca válidos en kaupamex ---
# arc42 / .claude/prds / .claude/epics / /task:create no existen en kaupamex.
# Se excluyen los docs del PROPIO auditor (describen los patrones que detecta →
# auto-FP; lección registro-errores-falsos-positivos FP-01).
SELF='(coherence-audit-gate|audit-coherence|thyrox-audit)\.md'
HARD=$(grep -rniE "\barc42\b|\.claude/prds|\.claude/epics|/task:create" \
        $CANON $CANON_DIRS 2>/dev/null | grep -vE "$SELF" | wc -l)
if [[ "$HARD" -eq 0 ]]; then ok "Lenguaje muerto (duro): 0 tokens de template ajeno"
else bad "Lenguaje muerto (duro): $HARD (arc42/.claude/prds/.claude/epics//task:create)"; fi

# --- 2b. Candidatos a deriva (WARN, no FAIL): triage cualitativo ---
# pm-thyrox/.thyrox/ROADMAP/now.md/type(scope) tienen menciones LEGÍTIMAS en
# kaupamex (notas de adaptación que explican qué NO usar). Detección mecánica
# no distingue uso-real de mención-documental -> son CANDIDATOS, los tría el
# agente increment-acceptor, no un FAIL automático (lección del dogfood inicial).
CAND=$(grep -rniE "pm-thyrox|\.thyrox/context|ROADMAP\.md|\bnow\.md\b|type\(scope\):" \
        $CANON $CANON_DIRS 2>/dev/null | grep -vE "$SELF" | wc -l)
if [[ "$CAND" -eq 0 ]]; then ok "Candidatos a deriva: 0"
else warn "Candidatos a deriva: $CAND menciones (pm-thyrox/.thyrox/ROADMAP/now.md/type(scope)) — triage cualitativo (muchas son notas de adaptación legítimas; revisar usos-como-instrucción en SKILL.md)"; fi

# --- 3. Coherencia de estado (SMD ↔ docs ↔ git) ---
SMD="$PARENT/kaupamex-docs/source/gestion/pm/siguiente-mejor-decision.rst"
if [[ -f "$SMD" ]]; then
    REF=$(grep -oE ':commit_referencia:.*docs [0-9a-f]{7}' "$SMD" | grep -oE '[0-9a-f]{7}$' | head -1)
    DOCSHEAD=$(git -C "$PARENT/kaupamex-docs" rev-parse --short=7 HEAD 2>/dev/null)
    FA=$(grep -oE ':fecha_actualizacion: [0-9T:-]+' "$SMD" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
    AGE=$(( ( $(date -u +%s) - $(date -u -d "${FA:-1970-01-01}" +%s 2>/dev/null || echo 0) ) / 86400 ))
    if [[ "$AGE" -gt 7 ]]; then warn "SMD: :fecha_actualizacion: $FA tiene >7 días — refrescar"
    else ok "SMD: fresco en el tiempo ($FA, ${AGE}d)"; fi
    if [[ -n "$REF" && -n "$DOCSHEAD" ]]; then
        if [[ "$REF" == "$DOCSHEAD" ]]; then ok "SMD: :commit_referencia: docs == HEAD ($REF)"
        else warn "SMD: :commit_referencia: docs $REF != docs HEAD $DOCSHEAD (deriva; +commits metadata tolerado)"; fi
    fi
else
    warn "SMD: no encontrado en $SMD (submódulo docs no clonado como hermano)"
fi
DIRTY=$(git status --short 2>/dev/null | wc -l)
if [[ "$DIRTY" -eq 0 ]]; then ok "Git super: árbol limpio (todo commiteado)"
else warn "Git super: $DIRTY archivos sin commitear"; fi

# --- 4. Anatomía oficial del skill thyrox ---
MISS=""
for d in SKILL.md scripts references assets; do
    [[ -e ".claude/skills/thyrox/$d" ]] || MISS="$MISS $d"
done
[[ -z "$MISS" ]] && ok "Anatomía: thyrox SKILL+scripts+references+assets presentes" \
                 || bad "Anatomía thyrox: faltan ->$MISS"

# --- 5. Coherencia parent ↔ submódulos (gitlink vs clon hermano) ---
if [[ -f .gitmodules ]]; then
    while read -r sm; do
        clone="$PARENT/kaupamex-$sm"
        link=$(git ls-tree HEAD "$sm" 2>/dev/null | awk '{print $3}')
        tip=$(git -C "$clone" rev-parse HEAD 2>/dev/null)
        if [[ -z "$tip" ]]; then warn "Submódulo $sm: clon hermano no hallado en $clone"
        elif [[ "$tip" == "$link" ]]; then ok "Submódulo $sm: gitlink == clon HEAD (${tip:0:7})"
        else bad "Submódulo $sm: gitlink ${link:0:7} != clon HEAD ${tip:0:7} (gitlink-bump-gate)"; fi
    done < <(git config -f .gitmodules --get-regexp path | awk '{print $2}')
else
    echo "N/A   · Submódulos: el proyecto no es multi-submódulo"
fi

# --- 6. Fechas fabricadas (ISO con hora redonda) en canónicos ---
FAB=$(grep -rhoE "T[0-9]{2}:00:00" $CANON $CANON_DIRS README.md 2>/dev/null | wc -l)
[[ "$FAB" -eq 0 ]] && ok "Timestamps: sin patrón de fabricación (THH:00:00) en canónicos" \
                  || warn "Timestamps: $FAB con hora redonda (THH:00:00) — revisar si son reales"

echo ""
echo "## Score: $PASS PASS · $FAIL FAIL · $WARN WARN"
[[ "$FAIL" -eq 0 ]] && echo "Veredicto mecánico: VERDE (el juicio cualitativo lo añade increment-acceptor)" \
                   || echo "Veredicto mecánico: hay FAIL — ver action plan"
$STRICT && [[ "$FAIL" -gt 0 ]] && exit 1
exit 0
