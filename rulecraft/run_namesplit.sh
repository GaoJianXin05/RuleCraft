#!/usr/bin/env bash
# The told prompt taken apart (NameOnly, NameVer) and the unnamed text condition on the hard set; one chain per
# provider, run side by side. Log: results/r2/log_namesplit.txt; each chain ends with a DONE line.
cd "$(dirname "$0")"
LOG=results/r2/log_namesplit.txt
NOW=$(date +%s)
{
  ALLOW_PEAK=1 PEAK_CAP_USD=3 PEAK_CAP_SINCE=$NOW WORKERS=8 python name_split_run.py --arms NameOnly,NameVer,TextUnnamed --reps 3
  echo "DONE deepseek"
} >> $LOG 2>&1 &
{
  LLM_PROFILE=solrun WORKERS=8 python name_split_run.py --arms NameOnly,NameVer --reps 3 --conflict-only-after 1 --budget 4
  LLM_PROFILE=solrun WORKERS=8 python name_split_run.py --arms TextUnnamed --reps 1 --budget 0.5
  echo "DONE solrun"
} >> $LOG 2>&1 &
{
  LLM_PROFILE=qwenflash WORKERS=8 python name_split_run.py --arms NameOnly,NameVer --reps 3 --budget 10
  LLM_PROFILE=qwenflash WORKERS=8 python name_split_run.py --arms TextUnnamed --reps 1 --budget 2
  echo "DONE qwenflash"
} >> $LOG 2>&1 &
{
  for p in qwenmax doubaopro doubaolite; do
    LLM_PROFILE=$p WORKERS=8 python name_split_run.py --arms TextUnnamed --reps 1 --budget 3
  done
  echo "DONE others"
} >> $LOG 2>&1 &
wait
echo ALLDONE >> $LOG
