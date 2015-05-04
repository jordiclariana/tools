#!/bin/bash

###### rltail ######
# Rotated Log Tail #
####################

print_help() {
  local myname="$(basename $0)"
  cat << EOF
Use: ${myname} [--dateformat <dateformat>] [--pattern <pattern>] [--number <number>] <fixpart> [<fixpart> ..]

 --dateformat <dateformat>    : For log files that its filename changing part is a date, specify the format as
                                'man date' FORMAT section. Default "%Y%m%d%H" (if no <number> specified)
 --number <number>            : If the filename changing part is just a incremental number. It can take the form of:
                                  1: It will generate 1,2,3,4,...
                                  01: It will generate 01,02,03,04...
                                  001: 001,002,003,004...
                                  And so on.
                                Default: Not defined.
 --pattern <pattern>          : Pattern of filename. Two special variables exist:
                                  %F: <fixpart>
                                  %D: <dateformat>
                                  %N: <number>
                                Default "%F-%D.log".
 <fixpart>                    : The part of the filename that does not change.

 NOTE: dateformat and number are mutually exclusive

Examples:
  ${myname} access
    Will tail access-2015043017.log, access-2015043018.log, ...
  ${myname} --number 01 --pattern "%F-%N.log" postfix
    Will tail postfix-01.log, postfix-02.log, ...
  ${myname} --number 05 --pattern "%F-%N.log" access error
    Will tail access-05.log and error-05.log, then access-06.log and error-06.log, ...
EOF
}

add_job() {
  local JOB=$1

  JOBS_LIST=("${JOBS_LIST[@]}" ${JOB})
}

del_job() {
  local JOB=$1
  local TMP_JOBS_LIST=("${JOBS_LIST[@]}")

  JOBS_LIST=()
  for job in "${TMP_JOBS_LIST[@]}"; do
    [ "$job" == "$JOB" ] &&  continue
    JOBS_LIST=$("${JOBS_LIST[@]}" "$job")
  done
}

kill_all_jobs() {
  for job in "${JOBS_LIST[@]}"; do
    kill %${job}
  done
  JOBS_LIST=()
}

generate_filenames() {
  FILESNAMES=()
  for cur_fixpart in "${FIXPART[@]}"; do
    FILENAME="$(echo "$PATTERN" | sed "s/%F/${cur_fixpart}/g;s/%D/${DATE}/g;s/%N/${NUMBER}/g")"
    if [ ! -f "${FILENAME}" ]; then
      return 1
    fi
    FILESNAMES=("${FILESNAMES[@]}" "${FILENAME}")
  done
}

stat_list_files() {
  local COUNT=0
  local TOTAL=${#FILESNAMES[@]}
  [ $TOTAL -eq 0 ] && return 1
  for file in "${FILESNAMES[@]}"; do
    if [ ! -e "$file" ]; then
      return 1
    fi
  done
}

remove_padding() {
  echo $1 | sed -r 's/^0+//'
}

FIXPART=

OOPTIONS=$(getopt  --longoptions "dateformat:,pattern:,number:,help" "h" "$@")
[ $? -eq 0 ] || exit 1
eval set -- "${OOPTIONS}"

while true; do
    case "$1" in
        --dateformat) DATEFORMAT=$2; shift 2 ;;
        --number)     NUMBER=$2; NUMBER_PADDING=${#NUMBER}; shift 2 ;;
        --pattern)    PATTERN=$2; shift 2 ;;
        --help|-h)    shift; print_help; exit 0;;
        --) shift 1; FIXPART=("$@"); break ;;
        *) echo "A: $@"; echo "Internal error!"; exit 1 ;;
    esac
done

if [ -z "${FIXPART[0]}" ]; then
  echo "No <fixpart> specified"
  exit 1
fi

if [ ! -z "$NUMBER" ] && [ ! -z "$DATEFORMAT" ]; then
  echo "Can't specify <number> and <dateformat> at the same time"
  exit 1
elif [ -z "$NUMBER" ]; then
  [ -z "$DATEFORMAT" ] && DATEFORMAT="%Y%m%d%H"
fi

[ -z "$PATTERN" ] && PATTERN="%F-%D.log"

trap 'kill_all_jobs; exit' INT TERM QUIT

exec 2> >(grep -v "Terminated")

DATE=$(date +"${DATEFORMAT}")

if ! generate_filenames; then
  echo "${FILENAME} file not found"
  exit 1
fi

while :; do
  if [ ! -z ${NUMBER} ]; then
    NUMBER=$(remove_padding $NUMBER)
    ((NUMBER++))
    NUMBER="$(printf "%0${NUMBER_PADDING}d" $NUMBER)"
  fi
  echo "===== Tailing ${FILESNAMES[@]} ====="
  for filename in "${FILESNAMES[@]}"; do
    tail -f "$filename" &
    JOBID=$(jobs | sed -r 's/^\[([0-9]+)\].*/\1/' | tail -n1)
    add_job $JOBID
  done
  KEEP_LOOPING=1
  while [ ${KEEP_LOOPING} -eq 1 ]; do
    sleep 1
    if [ ! -z ${NUMBER} ]; then
      generate_filenames
    else
      NEWDATE=$(date +"${DATEFORMAT}")
      if [ "${DATE}" != "${NEWDATE}" ]; then
        DATE=$NEWDATE
        generate_filenames
      else
        continue
      fi
    fi
    if stat_list_files; then
      kill_all_jobs
      KEEP_LOOPING=0
    fi
  done
done

