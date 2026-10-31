#!/usr/bin/env bash
# Contrato Consumer: PEP 8 e imports en TODO el Python versionado, sin baseline.
set -euo pipefail

project="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
root="$(git rev-parse --show-toplevel)"
cd "$root"
case "${1:-}" in
    --increment)
        shift
        exec uv run --frozen --project "$project" python \
            "$project/scripts/check_python_style_increment.py" "$@"
        ;;
    --staged)
        [[ $# == 1 ]] || exit 2
        ;;
    --all)
        [[ $# == 1 ]] || exit 2
        ;;
    *)
        echo 'Usage: check_python_style.sh --staged | --all | --increment ...' >&2
        exit 2
        ;;
esac

snapshot="$(mktemp -d)"
trap 'rm -rf -- "$snapshot"' EXIT
if [[ $1 == --staged ]]; then
    mapfile -d '' -t candidates < <(git ls-files --cached -z)
else
    mapfile -d '' -t candidates < <(
        git ls-files --cached --others --exclude-standard -z
    )
fi
declare -A executable_index=()
while IFS= read -r -d '' entry; do
    if [[ ${entry:0:6} == 100755 ]]; then
        executable_index["${entry#*$'\t'}"]=1
    fi
done < <(git ls-files --stage -z)
files=()
python_shebang='^#!.*[/[:space:]]python([0-9]+(\.[0-9]+)*)?([[:space:]]|$)'
for file in "${candidates[@]}"; do
    if [[ $file != *.py ]]; then
        if [[ $1 == --staged ]]; then
            [[ -n ${executable_index[$file]:-} ]] || continue
            IFS= read -r first_line < <(git show ":$file") || true
        else
            [[ -f $file && -x $file ]] || continue
            IFS= read -r first_line < "$file" || true
        fi
        [[ $first_line =~ $python_shebang ]] || continue
    fi
    files+=("$file")
done
if [[ ${#files[@]} == 0 ]]; then
    echo 'Python style: no Python sources; verification refused.' >&2
    exit 2
fi
for file in "${files[@]}"; do
    mkdir -p -- "$snapshot/$(dirname -- "$file")"
    if [[ $1 == --staged ]]; then
        git show ":$file" > "$snapshot/$file"
    else
        cp -- "$file" "$snapshot/$file"
    fi
done
cd "$snapshot"
uv run --frozen --project "$project" python -m pycodestyle \
    --ignore=W503 "${files[@]}"
uv run --frozen --project "$project" python \
    "$project/scripts/check_no_lazy_imports.py" --top-level "${files[@]}"
uv run --frozen --project "$project" python -W error::SyntaxWarning \
    -m py_compile "${files[@]}"
echo "Python style: PASS (${#files[@]} sources; complete import blocks)."
