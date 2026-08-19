#!/usr/bin/env bash
# run_agent.sh — ejecuta N tareas del backlog, una sesión limpia por tarea
set -uo pipefail
MAX=${1:-1}
mkdir -p tasks/done tasks/log

for _ in $(seq 1 "$MAX"); do
  TAREA=$(ls -1 tasks/backlog/*.md 2>/dev/null | head -n1)
  [ -z "$TAREA" ] && { echo "Backlog vacío."; exit 0; }
  ID=$(basename "$TAREA" .md)
  echo "▶ $ID"

  git checkout -B "task/$ID" >/dev/null 2>&1

  claude -p "$(cat "$TAREA")" \
    --model sonnet \
    --permission-mode acceptEdits \
    --allowedTools "Read,Write,Edit,Grep,Glob,Bash(pytest:*),Bash(ruff:*),Bash(mypy:*),Bash(git:*)" \
    --output-format stream-json --verbose \
    > "tasks/log/$ID.jsonl" 2> "tasks/log/$ID.err"
  RC=$?

  if grep -qiE "usage limit|rate.?limit" "tasks/log/$ID.err" "tasks/log/$ID.jsonl"; then
    echo "⏸ Límite de uso alcanzado en $ID. Reanuda cuando reinicie la ventana."; exit 2
  fi
  [ $RC -ne 0 ] && { echo "✗ Error en $ID (rc=$RC)"; exit 1; }

  if pytest -q && ruff check . && mypy backend/app; then
    git add -A && git commit -qm "$ID"
    mv "$TAREA" tasks/done/
    echo "✓ $ID — revisa el diff de task/$ID antes de mergear"
  else
    echo "✗ Calidad en rojo tras $ID. Rama task/$ID para revisión manual."; exit 1
  fi
done
