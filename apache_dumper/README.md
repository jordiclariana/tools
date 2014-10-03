Apache Dumper
=============

This program connects to a local or remote apache with "server-status" configured and parses, filters and prints the output.
If run locally it can also kill a process and even attach a debug tracer (ptrace) to extract the full request.
The main purpose of using the tracer is that the server-status module in Apache limits the request to 64 bytes (null char included).
Eventually, in order to debug or fix problems with unknown requests, you'll need to get full request.
The only way is to dump the apache process memory and look for the request. It can dump also the headers sent to Apache, the data if the request is a POST, etc.

DISCLAIMER: You should know that playing with memory is not safe, use debug tracer with caution.
            Using it on production is not recommended (although I've done it a lot :))
            Memory dump search can fail between Apache versions, let me know if it does not work for you.

You will need the following python modules:

 - Ptrace
 - Pycurl
 - argparse
 - lxml

Other modules should be included by default on regular distros.

```
usage: apache_dumper.py [-h] [-p PID] [-u URL] [-r REQUEST] [-n NOTREQUEST]
                        [-f PSTATUS [PSTATUS ...]] [-s STATUS [STATUS ...]]
                        [-t SECONDS] [-m BYTES] [-d] [-k]

Apache Memory Dumper

optional arguments:
  -h, --help            show this help message and exit
  -p PID, --pid PID     Process PID to show or dump the memory from. 0 means all PIDs
                        Default: 0
  -u URL, --url URL     Apache Status URL.
                        Of course, if not local, memory dump will fail.
                        Default: http://localhost/server-status
  -r REQUEST, --request REQUEST
                        Request to look for when dumping or showing (it is a regex).
                        Default: None (finds all processes)
  -n NOTREQUEST, --notrequest NOTREQUEST
                        Request to avoid when dumping or showing (it is a regex).
                        Default: None (finds all processes)
  -f PSTATUS [PSTATUS ...], --pstatus PSTATUS [PSTATUS ...]
                        Process status to look for when dumping or showing. Can be used multiple times.
                        Default: ['D', 'R', 'S', 'T', 'W', 'X', 'Z']
  -s STATUS [STATUS ...], --status STATUS [STATUS ...]
                        Status to look for when dumping or showing. Can be used multiple times. Only W and/or G can be used.
                        Default: ['W', 'G']
  -t SECONDS, --mintime SECONDS
                        Dump if process running time is at least mintime. 0 means all processes.
                        Default: 0
  -m BYTES, --maxmem BYTES
                        Dump if process memory is less than maxmem. 0 means no limit.
                        Default: 0
  -d, --dump            Dump process memory looking for pattern. Cannot be used with kill (-k|--kill) option.
                        WARNING: Active memory will be dumped, this can be dangerous and lead to unexpected behaviour.
                        Default: False
  -k, --kill            Kill apache processes that match. Cannot be used with dump (-d|--dump) option.
                        Default: False
```
