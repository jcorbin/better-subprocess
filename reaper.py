import errno
import os
import Queue
import time

from obituary import obituary

import logging
log = logging.getLogger(__name__)

listeners = []
reaped = {}
theReaper = None

class Reaper(object):
    def __init__(self, reap_pid=-1):
        self.reap_pid = reap_pid
        global theReaper
        theReaper = self

    def dispatch(self, obit):
        log.debug('dispatch ' + repr(obit))
        for listener in listeners:
            r = listener(obit)
            if r is True:
                del reaped[obit.pid]

    def reap(self, pid=None, wait=False):
        if pid is None: pid = self.reap_pid
        waittime = time.time()
        pid, status, rusage = os.wait4(pid, 0 if wait else os.WNOHANG)
        log.debug('wait4 => ' + repr((pid, status, rusage)))
        if pid != 0:
            reaped[pid] = obit = obituary(waittime, pid, status, rusage)
            self.dispatch(obit)
        return pid

    def handle_sigchld(self, signum, frame):
        log.debug('{0} handling SIGCHLD'.format(self.__class__.__name__))
        try:
            while True:
                pid = self.reap()
                log.debug('{0} SIGCHLD reaped pid {1}'
                    .format(self.__class__.__name__, pid))
                if pid == 0: break
        except OSError as err:
            if err.errno != errno.ECHILD: raise

class AsyncReaper(Reaper):
    def __init__(self):
        self.queue = Queue.Queue()
        super(AsyncReaper, self).__init__()
        self.dispatch = self.queue.put

    def process_queue(self):
        while True:
            try:
                obit = self.queue.get_nowait()
            except Queue.Empty:
                break
            super(AsyncReaper, self).dispatch(obit)

class ProcessRegistry(dict):
    def __init__(self, *args, **kwargs):
        listeners.append(self.dispatch)
        super(ProcessRegistry, self).__init__(*args, **kwargs)

    def __del__(self):
        listeners.remove(self.dispatch)

    def dispatch(self, obit):
        try:
            proc = self.pop(obit.pid)
        except KeyError:
            return None
        else:
            proc.handle_obituary(obit)

    def __setitem__(self, pid, proc):
        try:
            obit = reaped[pid]
        except KeyError:
            super(ProcessRegistry, self).__setitem__(pid, proc)
        else:
            proc.handle_obituary(obit)
