#!/usr/bin/env python

import paramiko, base64
import time, re, os
import signal, sys
import Queue
import threading
import argparse
from xml.dom import minidom

colors = {
    'nocolor': '\033[0m',
    'green':   '\033[32m',
    'red':     '\033[31m',
    'yellow':  '\033[33m',
    'white':   '\033[37m'
}

def parse_config(args):

  def set_conf_value(conf_item, from_user, default):
      if from_user:
          return from_user
      else:
          try:
              return type(default)(xmldoc.getElementsByTagName(conf_item)[0].firstChild.data)
          except (AttributeError, IndexError):
              return default

  def parse_host_param(host, configuration):
      this_host = { 'hostname': '',
                    'port': configuration['default_ssh_port'],
                    'username': configuration['default_ssh_username'],
                    'password': configuration['default_ssh_password'] }

      for param in host.split(','):
          (name, value) = param.split('=')
          if value:
              this_host[name] = type(this_host[name])(value)

      if this_host['hostname'] == '':
          raise Exception

      return this_host

  try:
    xmldoc = minidom.parse(os.path.expanduser(args.config_file))
  except:
    print("Unable to load configuration file {0}".format(args.config_file))
    return False

  configuration = {}

  configuration['queue_max_timeout']    = set_conf_value('queue_max_timeout', args.queuemaxtimeout, 0.5)
  configuration['ssh_timeout']          = set_conf_value('ssh_timeout', args.sshtimeout, 2.0)
  configuration['threshold_normal']     = set_conf_value('threshold_normal', args.thresholdnormal, 1.0)
  configuration['threshold_warning']    = set_conf_value('threshold_warning', args.thresholdwarning, 3.0)
  configuration['threshold_high']       = set_conf_value('threshold_high', args.thresholdhigh, 10.0)
  configuration['delay']                = set_conf_value('delay', args.delay, 1.0)
  configuration['default_ssh_port']     = set_conf_value('default_ssh_port', args.default_ssh_port, 22)
  configuration['default_ssh_username'] = set_conf_value('default_ssh_username', args.default_ssh_username, 'root')
  configuration['default_ssh_password'] = set_conf_value('default_ssh_password', args.default_ssh_password, '')

  configuration['hosts'] = []
  if args.host:
      for host in args.host:
          try:
              configuration['hosts'].append(parse_host_param(host, configuration))
          except:
              print("Invalid host found as command line parameter")
              sys.exit(1)
  else:
      xml_hosts = xmldoc.getElementsByTagName('host')
      for host in xml_hosts:
          if not 'hostname' in host.attributes.keys():
              print("Found host not properly configured. It has no 'hostname' attribute")
              continue
          host_string='hostname={hostname},port={port},username={username},password={password}'.format(
                       hostname = host.attributes['hostname'].value,
                       port     = host.attributes['port'].value if 'port' in host.attributes.keys() else '',
                       username = host.attributes['username'].value if 'username' in host.attributes.keys() else '',
                       password = host.attributes['password'].value if 'password' in host.attributes.keys() else '')
          configuration['hosts'].append(parse_host_param(host_string, configuration))

  return configuration

# Capture ctrl-c and exit
def signal_handler(signal, frame):
        print("\n")
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

# Functions to sort list with alphanumeric chars.
def atoi(text):
    return int(text) if text.isdigit() else text

def sort_by_hostname(element):
    return [ atoi(c) for c in re.split('(\d+)', element['hostname']) ]

# The thread function.
def createSshConnection(host, port, username, password, queue_in, queue_out):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    try:
        client.connect(hostname = host, username = username, port = port, password = password, timeout = configuration['ssh_timeout'])
    except:
        print("Problem connecting to " + host)

    # Inform the launcher that we pass the first connection attempt phase
    queue_out.put(host)

    # Main loop
    while True:
        try:
            command = queue_in.get() # Get the command to execute
            stdin, stdout, stderr = client.exec_command(command) # Send the command
            queue_out.put(stdout, True, configuration['queue_max_timeout']) # Send to main process the result of the command
        except (paramiko.SSHException, AttributeError): # Connection lost or timeout. Reconnect
            client.close()
            try:
                client.connect(hostname = host, username = username, port = port, password = password, timeout = configuration['ssh_timeout'])
            except: # We don't care if error, will try again later
                pass
        except Queue.Full: # No queue.get reach our queue.put
            pass
        except: # Unexpected error, inform and keep trying
            print("Unexpected error: ", sys.exc_info()[0])
            print(sys.exc_info()[1])
            print("Host: {0} | Command: {1}".format(host, command))

def getTerminalSize(): # This is not mine (http://stackoverflow.com/questions/566746/how-to-get-console-window-width-in-python)
    env = os.environ
    def ioctl_GWINSZ(fd):
        try:
            import fcntl, termios, struct, os
            cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,
        '1234'))
        except:
            return
        return cr
    cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
    if not cr:
        try:
            fd = os.open(os.ctermid(), os.O_RDONLY)
            cr = ioctl_GWINSZ(fd)
            os.close(fd)
        except:
            pass
    if not cr:
        cr = (env.get('LINES', 25), env.get('COLUMNS', 80))
    return int(cr[1]), int(cr[0])

def extract_average(average):
    if not average:
        return [ "N/A", "N/A", "N/A" ]
    else:
        m = re.match(r"^.*load average: ([0-9]+\.[0-9]+), ([0-9]+\.[0-9]+), ([0-9]+\.[0-9]+) *$", average)
        if m:
            return [ m.group(1), m.group(2), m.group(3) ]
        else:
            return [ "N/A", "N/A", "N/A" ]

def print_average(hostname, average):
    if average[0] == "N/A": # Server is up but not correct answer
        return str(colors['red'] + "{srv:" + max_hostname_length + "} {avg1:7} {avg2:7} {avg3:7}" + colors['nocolor']).format(srv=hostname + ":", avg1=average[0], avg2=average[1], avg3=average[2])
    else: # Format the output (colors, columns, ...)
        if float(average[0]) < configuration['threshold_normal']:
            color=colors['nocolor']
        elif float(average[0]) < configuration['threshold_warning']:
            color=colors['green']
        elif float(average[0]) < configuration['threshold_high']:
            color=colors['yellow']
        else:
            color=colors['red']
        return str("{srv:" + max_hostname_length + "} " + color + "{avg1:7} {avg2:7} {avg3:7}" + colors['nocolor']).format(srv=hostname + ":", avg1=average[0], avg2=average[1], avg3=average[2])

# Start main program

# Command line options parser
parser = argparse.ArgumentParser(description='Servers Load Average Screen', formatter_class = argparse.RawTextHelpFormatter)
parser.add_argument('-c', '--config_file', metavar = '<filename>', default = '~/.load.conf', type = str,
    help = 'Configuration file. Default: %(default)s')
parser.add_argument('-q', '--queuemaxtimeout', metavar = 'N', type = float,
    help = 'Max time for queues to wait for thread input and the other way around. Default: 0.5')
parser.add_argument('-s', '--sshtimeout', metavar = 'N', type = float,
    help = 'Max SSH connection timeout. Default: 0.5')
parser.add_argument('-0', '--thresholdnormal', metavar = 'N', type = float,
    help = 'Under this value the load is normal. It determines the color. Default: 1')
parser.add_argument('-1', '--thresholdhigh', metavar = 'N', type = float,
    help = 'Under this value the load is warning. It determines the color. Default: 3')
parser.add_argument('-2', '--thresholdwarning', metavar = 'N', type = float,
    help = 'Under this value the load is high. Above is critical. It determines the color. Default: 10')
parser.add_argument('-d', '--delay', metavar = 'N', type = float,
    help = 'Interval between updates. Default: 1')
parser.add_argument('-P', '--default_ssh_port', metavar = 'N', type = int,
    help = 'SSH port for all connections if not explicitly specified in the host. Default: 22')
parser.add_argument('-u', '--default_ssh_username', metavar = '<username>', type = str,
    help = 'Username for all connections if not explicitly specified in the host. Default: root')
parser.add_argument('-p', '--default_ssh_password', metavar = '<secret>', type = str,
    help = 'Password for all connections if not explicitly specified in the host. Default: None')

parser.add_argument('host', nargs = '*', type = str,
    help = 'Hosts to connect to. Overwrite config file list.\nUse as: hostname=<hostname>[,port=<port>][,username=<username>][,password=<password>]\nDefault: None')
args = parser.parse_args()

configuration = parse_config(args)

if not configuration:
    sys.exit(1)
# The connections pool
sshConnections = {}

# Queues pool. Two channels, in and out, request and response
queues_in  = {}
queues_out = {}

# For presentation purpouses
max_hostname_length = 0

if len(configuration['hosts']) == 0:
    print"No hosts configured"
    sys.exit(1)

# Order list by key hostname in dictionary
configuration['hosts'].sort(key=sort_by_hostname)

# Initialize all threads and connections.
os.system("clear")
threads = 0
sys.stdout.write('Threads: {0}/{1}'.format(threads, len(configuration['hosts'])))
sys.stdout.flush()
for host in configuration['hosts']:
    if len(host['hostname']) > max_hostname_length:
        max_hostname_length = len(host['hostname'])
    queues_in[host['hostname']] = Queue.Queue()
    queues_out[host['hostname']] = Queue.Queue()
    sshConnections[host['hostname']] = threading.Thread(
                                target = createSshConnection,
                                args = (
                                    host['hostname'],
                                    host['port'],
                                    host['username'],
                                    host['password'],
                                    queues_in[host['hostname']],
                                    queues_out[host['hostname']] )
                            )
    sshConnections[host['hostname']].daemon = True
    sshConnections[host['hostname']].start()

    threads = threads + 1
    sys.stdout.write("\rThreads: {0}/{1}".format(threads, len(configuration['hosts'])))
    sys.stdout.flush()

max_hostname_length = str(max_hostname_length + 2)

# Wait until all threads initialized
connected_hosts = 0
sys.stdout.write('\nConnecting: {0}/{1}'.format(connected_hosts, len(configuration['hosts'])))
sys.stdout.flush()
for host in configuration['hosts']:
    queues_out[host['hostname']].get()
    connected_hosts = connected_hosts + 1
    sys.stdout.write("\rConnecting: {0}/{1}".format(connected_hosts, len(configuration['hosts'])))
    sys.stdout.flush()
os.system("clear")

# Main process loop
while True:
    buff = []
    max_line_length = 0
    avg_load = [0, 0, 0, 0]
    for host in configuration['hosts']: # Get host by host uptime
        try:
            queues_in[host['hostname']].put('uptime', True, configuration['queue_max_timeout'])
            stdout = queues_out[host['hostname']].get(True, configuration['queue_max_timeout'])

            line = stdout.readlines()[0]
        except (Queue.Full, Queue.Empty, IndexError): # Server is down or bad response
            line = None

        num_avg = extract_average(line)
        new_line = print_average(host['hostname'], num_avg)
        buff.append(new_line)

        if len(new_line) > max_line_length:
            max_line_length = len(new_line)
        
        if num_avg[0] != "N/A":
            avg_load[0] = avg_load[0] + float(num_avg[0])
            avg_load[1] = avg_load[1] + float(num_avg[1])
            avg_load[2] = avg_load[2] + float(num_avg[2])
            avg_load[3] = avg_load[3] + 1

    if int(avg_load[3]) > 0:
        buff.append(print_average("\n\nTotal", [ round(avg_load[0]/avg_load[3], 2), round(avg_load[1]/avg_load[3], 2), round(avg_load[2]/avg_load[3], 2) ]))

    # Reset screen, no backscroll
    os.system("echo -ne '\\0033\\0143'")

    (width, height) = getTerminalSize()
    max_columns = width / ( max_line_length - 8 )
    # If it fits vertical, use the least columns possible
    for i in range(max_columns, 0, -1):
        if len(buff)/i <= height - 4:
            max_columns = i
    
    # Print
    for line in range(0, len(buff), max_columns if max_columns > 0 else 1):
        new_line = ""
        for i in range(0, max_columns):
            new_line = new_line + "{0} ".format(buff[line + i] if (line + i) < len(buff) else "")
        print(new_line)

    time.sleep(configuration['delay'])

