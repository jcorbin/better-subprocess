import errno
import os
import signal
import sys
from functools import wraps

import logging
logging.basicConfig(
    level=logging.INFO,
    datefmt='%FT%T', # YYYY-MM-DDTHH:MM:SS
    format='%(asctime)s.%(msecs)d [%(process)d.%(thread)d] %(name)s %(levelname)s %(message)s')

from collections import defaultdict
Outstanding = defaultdict(lambda: [])

def fork_run(run, *args, **kwargs):
    global Outstanding
    pid = os.fork()
    if pid == 0:
        run(*args, **kwargs)
        sys.exit(255)
    Outstanding[os.getpid()].append(pid)
    return pid

def forks(f):
    @wraps(f)
    def forker(*args, **kwargs):
        return fork_run(f, *args, **kwargs)
    return forker

def kill_pids():
    global Outstanding
    pids = Outstanding[os.getpid()]
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    killed = set()
    for pid in pids:
        try:
            os.kill(pid, 0)
        except OSError as err:
            if err.errno != errno.ESRCH:
                print >>sys.stderr, 'while trying to cleanup pid', pid, 'got', err
            continue
        os.kill(pid, signal.SIGKILL)
        killed.add(pid)
    while killed:
        pid, status = os.wait()
        killed.remove(pid)

import atexit
atexit.register(kill_pids)
