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

    kill_wait_delay = 0.001
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
        if self.poll() is not None: return
        if self.sequence is None:
            raise RuntimeError('unable to kill {0}'.format(self.pid))
        if not self.sequence:
            self.log.debug('sending last-ditch SIGKILL')
            self.sequence = None
            return self.send_signal(signal.SIGKILL)
        (delay, sig), self.sequence = self.sequence[0], self.sequence[1:]
        if delay is None:
            self.send_signal(sig)
        else:
            self._set_timer(delay, self.send_signal, sig)

    def send_signal(self, sig):
        if self.timer: self.timer.cancel()
        self.log.debug('sending signal ' + str(sig))
        os.kill(self.pid, sig)
        self._set_timer(self.kill_wait_delay, self.work)

    def _set_timer(self, delay, f, *args):
        if self.timer: self.timer.cancel()
        self.log.debug(
            '{0}s timer => {1}({2})'
            .format(delay, f, ','.join(map(repr, args))))
        self.timer = threading.Timer(delay, f, args=args)
        self.timer.start()

    def poll(self):
        if self.obituary is not None:
            return self.obituary
        waittime = time.time()
        pid, status, rusage = os.wait4(self.pid, os.WNOHANG)
        self.log.debug('poll wait wanted {0} got {1}'.format(self.pid, pid))
        if pid == self.pid:
            obit = obituary(waittime, pid, status, rusage)
            handle = reaper.theReaper.dispatch if reaper.theReaper \
                     else self.handle_obituary
            self.log.debug('dispatch to ' + repr(handle))
            handle(obit)
            return obit
        assert pid == 0

    def handle_obituary(self, obit):
        if self.obituary is None and obit.pid == self.pid:
            self.log.debug('got my obituary ' + repr(obit))
            self.obituary = obit
            if self.timer is not None:
                self.timer.cancel()
                del self.timer
            if self.callback:
                self.log.debug('calling ' + repr(self.callback))
                self.callback(obit)
            return obit
