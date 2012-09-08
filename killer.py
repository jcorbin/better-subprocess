import os
import signal
import threading
import time

import reaper
from obituary import obituary

import logging
log = logging.getLogger(__name__)

class Killer(object):
    registry = reaper.ProcessRegistry()

    obituary = None
    sequence = (
        (None, signal.SIGTERM),
        (.1,   signal.SIGKILL))
    timer = None

    def __init__(self, pid, sequence=None, callback=None):
        self.log = log.getChild(str(pid))
        self.pid = pid
        if sequence is not None:
            self.sequence = sequence
        self.callback = callback
        self.registry[self.pid] = self
        self.work()

    def work(self):
        if self.timer or self.poll() is not None: return

        if not self.sequence:
            self.log.debug('sending last-ditch SIGKILL')
            os.kill(self.pid, signal.SIGKILL)
            if not self.poll():
                raise RuntimeError('unable to kill {0}'.format(self.pid))
            return

        delay, sig = self.sequence[0]
        self.sequence = self.sequence[1:]

        if delay is None:
            self._send_signal(sig)
        else:
            self.timer = threading.Timer(delay,
                    self._send_signal, args=(sig,))
            self.timer.start()

    def _send_signal(self, sig):
        if self.timer:
            self.timer.cancel()
            del self.timer
        self.log.debug('sending signal ' + str(sig))
        os.kill(self.pid, sig)
        self.work()

    def poll(self):
        if self.obituary is not None:
            return self.obituary
        waittime = time.time()
        pid, status, rusage = os.wait4(self.pid, os.WNOHANG)
        self.log.debug('wait4 => ' + repr((pid, status, rusage)))
        if pid == self.pid:
            obit = obituary(waittime, pid, status, rusage)
            if reaper.theReaper:
                reaper.theReaper.dispatch(obit)
            else:
                self.handle_obituary(obit)
            return obit
        assert pid == 0

    def handle_obituary(self, obit):
        if self.obituary is not None and obit.pid == self.pid:
            self.obituary = obit
            if self.timer is not None:
                self.timer.cancel()
                del self.timer
            if self.callback:
                self.callback(obit)
            return obit
