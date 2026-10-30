#!/bin/bash
# Roadmap step 3: full A1 -> A3 -> A4 -> A5 pipeline for one seed at temperature 0.3.
S=$1; M=gpt-4.1-mini; PY=.venv/Scripts/python; C="--model $M --ids all --seed $S --temperature 0.3"
$PY -u harness/gc_runner.py run $C > data/cache/seed${S}_A1.log 2>&1
$PY -u harness/gc_runner.py selfdebug $C > data/cache/seed${S}_A3.log 2>&1
$PY -u harness/gc_pinpoint.py repair $C --base A1 --turns 3 > data/cache/seed${S}_A4.log 2>&1
$PY -u harness/gc_pinpoint.py repair $C --base A3 --turns 3 > data/cache/seed${S}_A5.log 2>&1
echo done $S
