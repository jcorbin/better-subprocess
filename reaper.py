import errno
import os
import Queue
import time

from obituary import obituary

class Reaper(object):
    def __init__(self, reap_pid=-1):
        self.reap_pid = reap_pid
        self.reaped = {}
        self.listeners = []

    def dispatch(self, obit):
        for listener in self.listeners:
            r = listener(obit)
            if r is True:
                del self.reaped[obit.pid]
                break

    def reap(self, pid=None, wait=False):
        if pid is None: pid = self.reap_pid
        waittime = time.time()
        pid, status, rusage = os.wait4(pid, 0 if wait else os.WNOHANG)
        if pid != 0:
            self.reaped[pid] = obit = obituary(waittime, pid, status, rusage)
            self.dispatch(obit)
        return pid

    def handle_sigcld(self, signum, frame):
        try:
            while self.reap() != 0:
                pass
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
    reaper = None

    def hookup(self, reaper):
        self.reaper = reaper
        self.reaper.listeners.append(self.dispatch)

    def unhookup(self):
        if self.reaper is not None:
            self.reaper.listeners.remove(self.dispatch)
            del self.reaper

    def dispatch(self, obit):
        try:
            proc = self.pop(obit.pid)
        except KeyError:
            return None
        else:
            proc._handle_obituary(obit)

    def __setitem__(self, pid, proc):
        if self.reaper is not None:
            try:
                obit = self.reaper.reaped[pid]
            except KeyError:
                pass
            else:
                proc._handle_obituary(obit)
                return
        super(ProcessRegistry, self).__setitem__(pid, proc)
