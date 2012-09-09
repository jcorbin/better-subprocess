from __future__ import division

import os
import reaper
import signal
import sys
import time

from test_util import forks

@forks
def fork_exit(exitstatus):
    sys.exit(exitstatus)

@forks
def sleep_forever():
    while True:
        signal.pause()

class Forked(object):
    registry = reaper.ProcessRegistry()

    def __init__(self, forked_pid):
        self.obit = None
        self.pid = forked_pid
        self.registry[self.pid] = self

    def handle_obituary(self, obit):
        self.obit = obit

def test_reaper():
    r = reaper.Reaper()
    assert r is reaper.theReaper

    pid = fork_exit(13)
    assert r.reap(pid, wait=True) == pid
    assert pid in reaper.reaped
    obit = reaper.reaped.pop(pid)
    assert obit.exitstatus == 13
    assert obit.termsig is None
    assert obit.stopsig is None
    assert obit.coredump is False

    pid = fork_exit(12)
    assert r.reap(-1, wait=True) == pid
    assert pid in reaper.reaped
    obit = reaper.reaped.pop(pid)
    assert obit.exitstatus == 12
    assert obit.termsig is None
    assert obit.stopsig is None
    assert obit.coredump is False

    pid = sleep_forever()
    assert r.reap(wait=False) == 0
    os.kill(pid, signal.SIGTERM)
    assert r.reap(wait=True) == pid
    assert pid in reaper.reaped
    obit = reaper.reaped.pop(pid)
    assert obit.exitstatus is None
    assert obit.termsig is signal.SIGTERM
    assert obit.stopsig is None
    assert obit.coredump is False

    got = {}
    def reap_listener(obit):
        got[obit.pid] = obit
        return True
    reaper.listeners.append(reap_listener)

    pid = fork_exit(0)
    assert r.reap(wait=True) == pid
    assert pid in got
    got = got[pid]
    assert got.pid == pid
    assert got.exitstatus == 0
    assert got.termsig is None
    assert got.stopsig is None
    assert got.coredump is False

    reaper.listeners.remove(reap_listener)

def test_registry():
    r = reaper.Reaper()

    f = Forked(fork_exit(0))
    assert r.reap(wait=True) == f.pid
    assert f.obit is not None
    assert f.obit.pid == f.pid
    assert f.obit.exitstatus == 0
    assert f.obit.termsig is None
    assert f.obit.stopsig is None
    assert f.obit.coredump is False

def test_asyncreaper():
    r = reaper.AsyncReaper()

    f = Forked(fork_exit(0))
    assert r.reap(wait=True) == f.pid
    assert f.obit is None
    assert r.queue.qsize() == 1
    r.process_queue()
    assert r.queue.qsize() == 0

    assert f.obit is not None
    assert f.obit.pid == f.pid
    assert f.obit.exitstatus == 0
    assert f.obit.termsig is None
    assert f.obit.stopsig is None
    assert f.obit.coredump is False

class DelayedExitFork(Forked):
    def __init__(self, expectedstatus, delay):
        self.delay = delay
        self.expectedstatus = expectedstatus
        super(DelayedExitFork, self).__init__(self.run())

    @forks
    def run(self):
        time.sleep(self.delay)
        sys.exit(self.expectedstatus)

def test_sigchld():
    r = reaper.Reaper()
    signal.signal(signal.SIGCHLD, r.handle_sigchld)

    waiting = [DelayedExitFork(i, (i % 32) / 32) for i in range(256)]
    while waiting:
        signal.pause()
        i = 0
        while i < len(waiting):
            if waiting[i].obit is not None:
                f = waiting.pop(i)
                assert f.obit.pid == f.pid
                assert f.obit.exitstatus == f.expectedstatus
                assert f.obit.termsig is None
                assert f.obit.stopsig is None
                assert f.obit.coredump is False
            else:
                i += 1

    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
