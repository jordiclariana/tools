#!/bin/bash

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

XML="$(cat << EOF
<?xml version="1.0" encoding="UTF-8"?>
<jnlp codebase="https://%%SERVERNAME%%:443" spec="1.0+">
<information>
  <title>iDRAC7 Virtual Console Client</title>
  <vendor>Dell Inc.</vendor>
   <icon href="https://%%SERVERNAME%%:443/images/logo.gif" kind="splash"/>
   <shortcut online="true"/>
 </information>
 <application-desc main-class="com.avocent.idrac.kvm.Main">
   <argument>ip=%%SERVERNAME%%</argument>
   <argument>vmprivilege=true</argument>
   <argument>helpurl=https://%%SERVERNAME%%:443/help/contents.html</argument>
   <argument>title=idrac%2C+Server%2C+User%3A+%%USERNAME%%</argument>
   <argument>user=%%USERNAME%%</argument>
   <argument>passwd=%%PASSWORD%%</argument>
   <argument>kmport=5900</argument>
   <argument>vport=5900</argument>
   <argument>apcp=1</argument>
   <argument>F2=1</argument>
   <argument>F1=1</argument>
   <argument>scaling=15</argument>
   <argument>minwinheight=100</argument>
   <argument>minwinwidth=100</argument>
   <argument>videoborder=0</argument>
   <argument>version=2</argument>
 </application-desc>
 <security>
   <all-permissions/>
 </security>
 <resources>
   <j2se version="1.6+"/>
   <jar href="https://%%SERVERNAME%%:443/software/avctKVM.jar" download="eager" main="true" />
 </resources>
 <resources os="Windows" arch="x86">
   <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOWin32.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMWin32.jar" download="eager"/>
 </resources>
 <resources os="Windows" arch="amd64">
   <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOWin64.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMWin64.jar" download="eager"/>
 </resources>
 <resources os="Windows" arch="x86_64">
   <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOWin64.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMWin64.jar" download="eager"/>
 </resources>
  <resources os="Linux" arch="x86">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux32.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux32.jar" download="eager"/>
  </resources>
  <resources os="Linux" arch="i386">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux32.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux32.jar" download="eager"/>
  </resources>
  <resources os="Linux" arch="i586">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux32.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux32.jar" download="eager"/>
  </resources>
  <resources os="Linux" arch="i686">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux32.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux32.jar" download="eager"/>
  </resources>
  <resources os="Linux" arch="amd64">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux64.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux64.jar" download="eager"/>
  </resources>
  <resources os="Linux" arch="x86_64">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOLinux64.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMLinux64.jar" download="eager"/>
  </resources>
  <resources os="Mac OS X" arch="x86_64">
    <nativelib href="https://%%SERVERNAME%%:443/software/avctKVMIOMac64.jar" download="eager"/>
   <nativelib href="https://%%SERVERNAME%%:443/software/avctVMMac64.jar" download="eager"/>
  </resources>
</jnlp>

EOF
)"

TMPFILE="$(mktemp)"
echo "${XML}" | sed 's/%%SERVERNAME%%/'${HOSTNAME}'/g;s/%%USERNAME%%/'${USERNAME}'/g;s/%%PASSWORD%%/'${PASSWORD}'/g' > "${TMPFILE}"
${JAVAWS} "${TMPFILE}"
sleep 1
rm -f "${TMPFILE}"

