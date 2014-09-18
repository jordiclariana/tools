#!/usr/bin/env python

import sys
import os, signal
import re
from ptrace.debugger import PtraceDebugger
from ptrace.debugger.memory_mapping import readProcessMappings
import StringIO
import pycurl
from lxml import etree
import argparse

from pprint import pprint

def fnd(f, pattern, start=0):
    # Get f size
    f.seek(0, os.SEEK_END)
    fsize=f.tell()
    f.seek(0)

    bsize = 4096
    buffer = None

    if start > 0:
        f.seek(start)
    overlap = len(pattern) - 1
    while True:
        if (f.tell() >= overlap and f.tell() < fsize):
            f.seek(f.tell() - overlap)
        buffer = f.read(bsize)
        if buffer:
            pos = buffer.find(pattern)
            if pos >= 0:
                return f.tell() - (len(buffer) - pos)
        else:
            return -1

def get_fragment(f, start, end):
    f.seek(start)
    print_len=end-start
    buffer=f.read(print_len)
    return buffer

def get_apache_process(url = "http://localhost/server-status", re_status = "W|G", pid = 0, request_pattern = "", mintime = 0, re_pstatus = "D|R|S|T|W|X|Z"):
    status_pattern  = re.compile(re_status)
    pstatus_pattern = re.compile(re_pstatus)
    #num_pattern = re.compile("[0-9]+")
    buffer=StringIO.StringIO()

    curl = pycurl.Curl()
    curl.setopt(pycurl.URL, url)
    curl.setopt(pycurl.WRITEFUNCTION, buffer.write)
    curl.setopt(pycurl.FOLLOWLOCATION, 1)
    curl.setopt(pycurl.MAXREDIRS, 5)
    curl.setopt(pycurl.NOSIGNAL, 1)

    curl.perform()
    curl.close()

    xpath = etree.HTML(buffer.getvalue())
    tables = xpath.xpath('//table[1]/tr[position()>1]')
    
    found = False

    processes_list = {}
    for tr in tables:
        tds = tr.xpath('td')
        b = tds[3].xpath('b')
        if len(b)>0:
            cstatus = b[0].text.strip()
        else:
            cstatus = tds[3].text.strip()

        try:
            for line in open("/proc/%d/status" % int(tds[1].text)).readlines():
                if line.startswith("State:"):
                    pstatus = line.split(":",1)[1].strip().split(' ')[0]
        except ValueError:
            pstatus = '=' # Means nothing, just not to match the regex
        except IOError:
            # Too bad process do not exist any more
            pstatus = '='

        if status_pattern.match(cstatus) and pstatus_pattern.match(pstatus):
            if int(tds[5].text) < mintime: # Mintime too low
                continue
            if request_pattern and not re.search(request_pattern, tds[12].text):    # Not the URL we are looking for
                continue

            if tds[10].text == '127.0.0.1' and re.search('^GET /server-status', tds[12].text):
                continue

            if pid > 0 and int(tds[1].text) == pid:
                found = True
                processes_list[int(tds[1].text)] = { 'pid': int(tds[1].text), 'time': tds[5].text, 'status': cstatus, 'request': tds[12].text,
                                                    'client': tds[10].text, 'vhost': tds[11].text, 'pstatus': pstatus }
            elif pid == 0:
                processes_list[int(tds[1].text)] = { 'pid': int(tds[1].text), 'time': tds[5].text, 'status': cstatus, 'request': tds[12].text,
                                                    'client': tds[10].text, 'vhost': tds[11].text, 'pstatus': pstatus }
    if pid > 0 and not found:
        print("PID {0} not found".format(pid))
        return False
    return processes_list

def print_process (process, decorator = ""):
    print((((decorator + " ") if decorator else "") + "Pid: {0:5} | PStatus: {1} | Status: {2} | Time: {3:5} | VHost: {4} | Client: {5} | Request: {6}" + ((" " + decorator if decorator else ""))).format(
            process['pid'], process['pstatus'], process['status'], process['time'], process['vhost'], process['client'],
            process['request']))

def kill (process):
    print_process(process)
    os.kill(process['pid'], signal.SIGKILL)

def do_dump (process, maxmem):
    print_process (process, "===")

    # Attach to the process
    debugger = PtraceDebugger()
    try:
        d_process = debugger.addProcess(process['pid'], False)
    except:
        print("Error attaching to the process pid {0}. Aborting".format(process['pid']))
        sys.exit(1)

    d_process.was_attached = True
    procmaps = readProcessMappings(d_process)
    # Look for process heap region
    for pm in procmaps:
        if pm.pathname == None:
            mem_start=pm.start
            mem_end=pm.end
            mem_total=mem_end-mem_start

            if maxmem > 0 and mem_total > maxmem :
                print("Process memory is {0} but you defined maxmem to {1}".format(mem_total, maxmem))
                return False

            # Use StringIO to work only in memory. This can be dangerous, because "heap" can be big.
            the_mem = StringIO.StringIO()
            # Transfer process heap memory to the_mem var.
            the_mem.write(d_process.readBytes(mem_start, mem_total))
            # We have what we were looking for. Let's detach the process.
            d_process.detach()

            # Start search
            request_end=0
            found=False
            while True:
                hdr_pos=fnd(the_mem, process['request'], request_end)
                if hdr_pos==-1: # EOF
                    break
                request_pos=hdr_pos # This is the start of the possible match
                request_end=fnd(the_mem, "\x00", request_pos) # This is the end of the possible match
                # If we find double new line then this should be a valid request and data block.
                if fnd(the_mem,"\x0d\x0a\x0d\x0a", request_pos) < request_end:
                    found=True
                    # If valid, print it!
                    print get_fragment(the_mem, request_pos, request_end)
                # Prepare to continue searching
                the_mem.seek(request_end+1)

            the_mem.close()
            if found:
                break

parser = argparse.ArgumentParser(description='Apache Memory Dumper', formatter_class = argparse.RawTextHelpFormatter)
parser.add_argument('-p', '--pid', metavar = 'PID', default = 0, type = int,
    help = 'Process PID to show or dump the memory from. 0 means all PIDs\nDefault: %(default)s')
parser.add_argument('-u', '--url', metavar = 'URL', default = 'http://localhost/server-status',
    help = 'Apache Status URL.\nOf course, if not local, memory dump will fail.\nDefault: %(default)s')
parser.add_argument('-r', '--request', metavar = 'REQUEST', default = None,
    help = 'Request to look for when dumping or showing (it is a regex).\nDefault: None (finds all processes)')
parser.add_argument('-f', '--pstatus', metavar = 'PSTATUS', default = [ 'D', 'R', 'S', 'T', 'W', 'X', 'Z' ],
    help = 'Process status to look for when dumping or showing. Can be used multiple times.\nDefault: %(default)s',
    nargs = '+', choices = [ 'D', 'R', 'S', 'T', 'W', 'X', 'Z' ])
parser.add_argument('-s', '--status', metavar = 'STATUS', default = [ 'W', 'G' ],
    help = 'Status to look for when dumping or showing. Can be used multiple times. Only W and/or G can be used.\nDefault: %(default)s',
    nargs = '+', choices = [ 'W', 'G' ])
parser.add_argument('-t', '--mintime', metavar = 'SECONDS', default = 0, type = int,
    help = 'Dump if process running time is at least mintime. 0 means all processes.\nDefault: %(default)s')
parser.add_argument('-m', '--maxmem', metavar = 'BYTES', default = 0, type = int,
    help = 'Dump if process memory is less than maxmem. 0 means no limit.\nDefault: %(default)s')
parser.add_argument('-d', '--dump', metavar = 'DUMP', action = 'store_const', const = True, default = False,
    help = 'Dump process memory looking for pattern. Cannot be used with kill (-k|--kill) option.\nWARNING: Active memory will be dumped, this can be dangerous and lead to unexpected behaviour.\nDefault: %(default)s')
parser.add_argument('-k', '--kill', metavar = 'KILL', action = 'store_const', const = True, default = False,
    help = 'Kill apache processes that match. Cannot be used with dump (-d|--dump) option.\nDefault: %(default)s')
args = parser.parse_args()

if args.dump and args.kill:
    print ("Cannot kill and dump. Choose one option only.")

args.status = '|'.join(args.status)
args.pstatus = '|'.join(args.pstatus)

processes_list = get_apache_process(url = args.url, re_status = args.status, pid = args.pid, request_pattern = args.request, mintime = args.mintime, re_pstatus = args.pstatus)

if processes_list:
    if args.dump:
        if args.pid > 0:
            do_dump(process = processes_list[args.pid], maxmem = args.maxmem)
        else:
            for pid in processes_list.keys():
                do_dump(process = processes_list[pid], maxmem = args.maxmem)
    elif args.kill:
        print ("Killing processes...")
        for pid in processes_list.keys():
            kill(processes_list[pid])
        print ("Done")
    else:
        for pid in processes_list.keys():
            print_process(processes_list[pid])
else:
    print("No processes found.")

sys.exit(0)
