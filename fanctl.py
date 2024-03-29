#!/bin/python
# -*- coding: utf-8 -*-

# Fan Control program for Dell servers
# tested on R630 with e5-2697a V4
#
# WARNING - Temp ranges are specific to the TDP of my CPU
#           Please go to intel ARK for your CPU and check the
#           TDP (Thermal Design Power)
#           then subtract about 15 degrees C for returntoauto
#
# Modified form orginal version to use systemd journal
#
# fanctl.py
# start program using fanctlinit.sh
#     /var/opt/fanctlinit.sh {start|stop|restart|status}

# Input - none, paramters are embeded in script
# Output - send all messages to syslog (/var/log/fanctl.log)

__author__ = 'Garrett Gauthier'
__copyright__ = 'Copyright 2022, Garrett Gauthier'
__credits__ = ['Garrett Gauthier', 'Others soon?']
__license__ = 'GNU 3.0'
__version__ = '1.2'
__versiondate__ = '10/09/2022'
__maintainer__ = 'gauthig@github'
__github__ = 'https://github.com/gauthig/dellfanctl'
__status__ = 'Production'
__app__ = 'fanctl'

import sys
import re
import time
import subprocess
import logging
import syslog
import systemd.journal

pausetime = 10
ipmiexe = "/usr/bin/ipmitool"
temp = 0.0
prevtemp = 0.0
logmsg = ""

# PIDFILE is only used if you started this via a start service script
PIDFILE = "/var/run/fanctl.pid"
# User variable based on your system / CPU
# Temps are in Celsius
# To change speed setting, change only the last two digits in hex.
# Speeds are percentage of full power in Hex, i.e 46 = 70% power, 15 = 20%
fanauto = "0x30 0x30 0x01 0x01"  # Let the BIOS manage fan speed
# fanmanual=["0x30", "0x30", "0x01", "0x00"] #Enable manual/static fan speed
fanmanual = " 0x30 0x30 0x01 0x00 "
returntoauto = 62.0  # sets temp to return automatic control to the BIOS
temp1 = 38.0
temp2 = 42.0
temp3 = 48.0
temp4 = 52.0
fanspeed0 = "0x30 0x30 0x02 0xff 0x10"  # Default speed
fanspeed1 = "0x30 0x30 0x02 0xff 0x14"  # Greater than or equal to temp1
fanspeed2 = "0x30 0x30 0x02 0xff 0x1f"  # Greater than or equal to temp2
fanspeed3 = "0x30 0x30 0x02 0xff 0x2a"  # Greater than or equal to temp3
fanspeed4 = "0x30 0x30 0x02 0xff 0x46"  # Greater than or equal to temp4
ipmiuser = "IPMI User"
ipmipassword = "ipmipassword"
ipmihost = "server.com or Ip address"

ipmistr = ipmiexe + " -I lanplus -H " + ipmihost + \
    " -U " + ipmiuser + " -P " + ipmipassword


def autofan():
    subprocess.run(ipmistr + ' raw ' + [hex(fanauto)], capture_output=True)

def setfanspeed(setspeed):
    # First ensrue IPMI is set to manual/static fan setting
    fanmode = 'static'
    ipmiproc = ipmistr + " raw " + fanmanual
    p = subprocess.Popen(ipmiproc, stdout=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    p_status = p.wait()

    # Second set the static speed
    ipmiproc = ipmistr + " raw " + setspeed
    p = subprocess.Popen(ipmiproc, stdout=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    p_status = p.wait()
    logmsg = "Detected threshold change from " + \
        str(prevtemp) + "C to " + str(temp) + "C"
    log_info_records( logmsg)
    logmsg = "Set fan speed to " + setspeed[-4:]
    log_info_records( logmsg)

def getcputemp():
    curtemp = 0
    try:
        ipmiproc = ipmistr + " sensor reading Temp"
        p = subprocess.Popen(ipmiproc, stdout=subprocess.PIPE, shell=True)
        (output, err) = p.communicate()
        p_status = p.wait()
        parsetemp = re.compile('(\d+(\.\d+)?)')
        curtemp = float(parsetemp.search(output.decode()).group())
    except Exception as ipmierror:
        autofan()
        logmsg = "Cannot get IPMI temp"
        log_error_records( logmsg)
    return curtemp

def log_info_records(message):
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__app__)
    
    systemd.journal.send(message, SYSLOG_IDENTIFIER='my_app')

def log_error_records(message):
    logging.basicConfig(level=logging.ERROR)
    logger = logging.getLogger(__app__)
    
    systemd.journal.send(message, SYSLOG_IDENTIFIER='my_app')

if __name__ == '__main__':
    fanmode = "static"
    logmsg = "Starting fan control - Interval of " + str(pausetime)
    log_info_records( logmsg)
    while True:
        try:
            temp = getcputemp()
        except Exception as ipmierror:
            autofan()
            logmsg = "Cannot get IPMI temp"
            log_error_records( logmsg)

        if temp != prevtemp:
            try:
                if temp >= returntoauto and fanmode == "static":
                    autofan()
                    fanmode = "auto"
                elif temp >= temp4 and prevtemp < temp4:
                    setfanspeed(fanspeed4)
                elif temp >= temp3 and prevtemp < temp3:
                    setfanspeed(fanspeed3)
                elif temp >= temp2 and prevtemp < temp2:
                    setfanspeed(fanspeed2)
                elif temp >= temp1 and prevtemp < temp1:
                    setfanspeed(fanspeed1)
                elif temp < temp1:
                    setfanspeed(fanspeed0)
            except Exception as ipmierror:
                autofan()
                logmsg = "Setting fan speed failed"
                log_error_records( logmsg)
        prevtemp = temp
        time.sleep(pausetime)

sys.exit()
