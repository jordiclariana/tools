#!/bin/bash

CURL="$(which curl)"
if [ -z ${CURL} ]; then
    echo "No 'curl' found. Install it"
    exit 1
fi

JAVAWS="$(which javaws)"

if [ -z ${JAVAWS} ]; then
    echo "No 'javaws' found. Install it"
    exit 1
fi

print_help() {
    echo "Use:"
    echo -e "    $0 -h <hostname> -u <username> -p <password>"
}

while getopts ":u:p:h:" opt; do
  case $opt in
    u)
      USERNAME="${OPTARG}"
    ;;
    p)
      PASSWORD="${OPTARG}"
    ;;
    h)
      HOSTNAME="${OPTARG}"
    ;;
    :)
        echo "Error: -${OPTARG} needs an argument"
        print_help
        exit 1
    ;;
  esac
done

if [ -z ${USERNAME} ] || [ -z ${PASSWORD} ] || [ -z ${HOSTNAME} ]; then
    print_help
    exit 1
fi

SC=$(${CURL} -s -k "https://${HOSTNAME}/rpc/WEBSES/create.asp?WEBVAR_USERNAME=${USERNAME}&WEBVAR_PASSWORD=${PASSWORD}" | grep "SESSION_COOKIE" | sed -r 's/.*: '\''([^'\'']*)'\''.*/\1/')

if [ "${SC}" == "" ]; then
    echo "No cookie acquired"
    exit 1
fi

TMPFILE=$(mktemp)
${CURL} -s -k -b "SessionCookie=${SC}" "https://${HOSTNAME}/Java/jviewer.jnlp" -o "${TMPFILE}"

${JAVAWS} "${TMPFILE}"
sleep 1
rm -f "${TMPFILE}"

