#!/bin/bash
# Roadmap step 5: second model on the GitChameleon dev subset (bounded cost): A1 -> A3 -> A4 -> A5.
M=$1; PY=.venv/Scripts/python; C="--model $M --ids dev"
$PY -u harness/gc_runner.py run $C > data/cache/m_${M}_A1.log 2>&1
$PY -u harness/gc_runner.py selfdebug $C > data/cache/m_${M}_A3.log 2>&1
$PY -u harness/gc_pinpoint.py repair $C --base A1 --turns 3 > data/cache/m_${M}_A4.log 2>&1
$PY -u harness/gc_pinpoint.py repair $C --base A3 --turns 3 > data/cache/m_${M}_A5.log 2>&1
echo done
