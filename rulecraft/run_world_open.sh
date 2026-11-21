#!/bin/bash
# Open recognition probe on the 1,240 Minecraft images, six core models; caps are cumulative per model.
cd "$(dirname "$0")"
LOG=results/r2/log_world_open.txt
NOW=$(python -c "import time;print(time.time())")
one() { LLM_PROFILE=$1 WORKERS=8 SPEND_CAP_USD=$2 python world_open.py >> $LOG 2>&1; }
ALLOW_PEAK=1 PEAK_CAP_USD=1 PEAK_CAP_SINCE=$NOW LLM_PROFILE=deepseek WORKERS=8 python world_open.py >> $LOG 2>&1 &
one qwenmax 17.5 &
one qwenflash 117 &
one doubaopro 22.5 &
one doubaolite 5 &
one solrun 46 &
wait
echo ALLDONE >> $LOG
