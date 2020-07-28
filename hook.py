import frida
import time
import os
import sys
import optparse
import threading
import codecs
import shutil
import tempfile
import subprocess
import re

import paramiko
from paramiko import SSHClient
from scp import SCPClient
from tqdm import tqdm
import traceback

print ('''\033[1;31m \n
_|      _|                      _|                  _|      
_|_|    _|    _|_|      _|_|    _|_|_|    _|_|_|    _|  _|  
_|  _|  _|  _|    _|  _|    _|  _|    _|  _|    _|  _|_|    
_|    _|_|  _|    _|  _|    _|  _|    _|  _|    _|  _|  _|  
_|      _|    _|_|      _|_|    _|_|_|    _|_|_|    _|    _|
        https://noobpk.github.io          _|                 
Trace Class/Func & Modify Return Value    _|   #noobteam
''')

print ("\033[1;34m[*]___author___: @noobpk\033[1;37m")
print ("\033[1;34m[*]___version___: 1.1\033[1;37m")
print ("")

def start_frida_server():
    fs = "/data/local/tmp/frida-server*"
    isFs = os.system('adb shell ls ' + fs +' 1> /dev/null')
    if (isFs != 0):
        print("\033[1;31m[-] Frida Server Not Found!!\033[1;31m")
    else:
        fsName = os.popen('adb shell ls ' + fs + '| grep frida-server').read()
        print('\033[1;32m[*] Found Frida Server: \033[1;32m'+ fsName)
        isProc = os.popen('adb shell ps | grep frida-server').read()
        if (isProc):
            print("\033[1;33m[!] Frida Server Is Running\033[1;33m")
        else:
            print("[\033[1;32m*] Start Frida Server...\033[1;32m")
            os.system('adb shell chmod +x ' + fs)
            os.system('adb shell ' + fs + ' &')
            time.sleep(5)
            isProc = os.popen('adb shell ps | grep frida-server').read()
            if (isProc):
                print("\033[1;32m[*] Frida Server Start Success!!\033[1;32m")
            else:
                print("\033[1;31m[-] Frida Server Start Failed!! Check & Try Again\033[1;31m")

def stop_frida_server():
    fs = "/data/local/tmp/frida-server*"
    isProc = os.popen('adb shell ps | grep frida-server').read()
    if (isProc):
        print("\033[1;32m[*] Found Process Frida Server:\n\033[1;32m" + isProc)
        print("\033[1;32m[*] Stop Frida Server...\033[1;32m")
        os.system('adb shell pkill -f ' + fs)
        time.sleep(5)
        print("\033[1;32m[*] Stop Frida Server Success!!\033[1;32m")
    else:
        print("\033[1;33m[!] Frida Server Not Start\033[1;33m")

def get_usb_iphone():
    Type = 'usb'
    if int(frida.__version__.split('.')[0]) < 12:
        Type = 'tether'
    device_manager = frida.get_device_manager()
    changed = threading.Event()

    def on_changed():
        changed.set()

    device_manager.on('changed', on_changed)

    device = None
    while device is None:
        devices = [dev for dev in device_manager.enumerate_devices() if dev.type == Type]
        if len(devices) == 0:
            print('[?] Waiting for USB device...')
            changed.wait()
        else:
            device = devices[0]

    device_manager.off('changed', on_changed)

    return device

def compare_applications(a, b):
    a_is_running = a.pid != 0
    b_is_running = b.pid != 0
    if a_is_running == b_is_running:
        if a.name > b.name:
            return 1
        elif a.name < b.name:
            return -1
        else:
            return 0
    elif a_is_running:
        return -1
    else:
        return 1

def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function"""

    class K:
        def __init__(self, obj):
            self.obj = obj

        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0

    return K

def get_applications(device):
    try:
        applications = device.enumerate_applications()
    except Exception as e:
        sys.exit('\033[1;31m[-] Failed to enumerate applications: %s\033[1;31m' % e)

    return applications

def list_applications(device):
    applications = get_applications(device)

    if len(applications) > 0:
        pid_column_width = max(map(lambda app: len('{}'.format(app.pid)), applications))
        name_column_width = max(map(lambda app: len(app.name), applications))
        identifier_column_width = max(map(lambda app: len(app.identifier), applications))
    else:
        pid_column_width = 0
        name_column_width = 0
        identifier_column_width = 0

    header_format = '%' + str(pid_column_width) + 's  ' + '%-' + str(name_column_width) + 's  ' + '%-' + str(
        identifier_column_width) + 's'
    print(header_format % ('PID', 'Name', 'Identifier'))
    print('%s  %s  %s' % (pid_column_width * '-', name_column_width * '-', identifier_column_width * '-'))
    line_format = '%' + str(pid_column_width) + 's  ' + '%-' + str(name_column_width) + 's  ' + '%-' + str(
        identifier_column_width) + 's'
    for application in sorted(applications, key=cmp_to_key(compare_applications)):
        if application.pid == 0:
            print(line_format % ('-', application.name, application.identifier))
        else:
            print(line_format % (application.pid, application.name, application.identifier))

def main():
    usage = "Usage: python3 %prog [options] arg\n\rExample: python3 hook.py -p com.android.vending -s trace_class.js"
    parser = optparse.OptionParser(usage,add_help_option=False)
    parser.add_option('-h', "--help", action="help", dest="help", help="Show basic help message and exit")
    parser.add_option("-p", "--package", dest="package",
                    help="Bundle identifier of the target app", metavar="PACKAGE", action="store", type="string")
    parser.add_option("-s", "--script", dest="script",
                    help="Frida Script Hooking", metavar="SCIPRT.JS")
    parser.add_option("--fs-start",
                    action="store_true", help="Start frida server", dest="startfs")
    parser.add_option("--fs-stop",
                    action="store_true", help="Stop frida server", dest="stopfs")
    parser.add_option("--listapp",
                    action="store_true", help="List the installed apps", dest="listapp")    
    options, args = parser.parse_args()
    try:
        if options.startfs:
            get_usb_iphone()
            start_frida_server()

        elif options.stopfs:
            get_usb_iphone()
            stop_frida_server()

        elif options.listapp:
            device = get_usb_iphone()
            list_applications(device)

        elif options.package and options.script:
            print('[*] Spawning: ' + options.package)
            print('[*] Script: ' + options.script)
            pid = frida.get_usb_device().spawn(options.package)
            session = frida.get_usb_device().attach(pid)
            hook = open(options.script, 'r')
            script = session.create_script(hook.read())
            script.load()
            frida.get_usb_device().resume(pid)
            sys.stdin.read()
            print('---------------Hook---Done---------------')
            sys.exit(0)

        else:
            print("[-] specify the options. use (-h) for more help!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("[:)] Bye!!")
        sys.exit(0)

if __name__ == '__main__':
        main()

    