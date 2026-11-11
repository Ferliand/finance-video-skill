#!/usr/bin/env bash
# Pasang skill ke Claude Code, Antigravity, dan/atau Pi.
#   ./scripts/install.sh --all                 # global (home), salin
#   ./scripts/install.sh --claude --pi --link  # symlink supaya ikut ter-update
#   ./scripts/install.sh --all --project ~/kerja/proyek-saya   # level proyek
set -euo pipefail

NAME="finance-video-script"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/$NAME"
targets=(); link=0; project=""

while [ $# -gt 0 ]; do
  case "$1" in
    --claude) targets+=(claude) ;;
    --antigravity) targets+=(antigravity) ;;
    --pi) targets+=(pi) ;;
    --all) targets=(claude antigravity pi) ;;
    --link) link=1 ;;
    --project) project="${2:?--project butuh folder}"; shift ;;
    *) echo "Argumen tidak dikenal: $1" >&2; exit 2 ;;
  esac
  shift
done
[ ${#targets[@]} -gt 0 ] || { echo "Pilih --claude, --antigravity, --pi, atau --all" >&2; exit 2; }
[ -f "$SRC/SKILL.md" ] || { echo "SKILL.md tidak ditemukan di $SRC" >&2; exit 1; }

dest_for() {
  local base="${project:-$HOME}"
  if [ -n "$project" ]; then
    case "$1" in
      claude) echo "$base/.claude/skills" ;;
      antigravity) echo "$base/.agents/skills" ;;
      pi) echo "$base/.pi/skills" ;;
    esac
  else
    case "$1" in
      claude) echo "$base/.claude/skills" ;;
      antigravity) echo "$base/.gemini/config/skills" ;;
      pi) echo "$base/.pi/agent/skills" ;;
    esac
  fi
}

for t in "${targets[@]}"; do
  dir="$(dest_for "$t")"
  mkdir -p "$dir"
  rm -rf "${dir:?}/$NAME"
  if [ "$link" = 1 ]; then ln -s "$SRC" "$dir/$NAME"; else cp -R "$SRC" "$dir/$NAME"; fi
  echo "[$t] -> $dir/$NAME"
done
echo "Selesai. Mulai ulang sesi agen agar skill terdeteksi."
