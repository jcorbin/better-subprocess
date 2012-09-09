import os
import Queue
import signal
import sys
from itertools import product

import logging
log = logging.getLogger(__name__)

import killer
from test_util import forks

import time

@forks
def echo_signals(w, signals, exiton=set(), delayexit=None):
    shouldexit = []
    def handler(signum, frame):
        if signum in exiton:
            os.write(w, 'exiton %d\n' % signum)
            shouldexit.append(signum)
            return
        os.write(w, 'got %d\n' % signum)
    for sig in signals:
        signal.signal(sig, handler)
    os.write(w, 'ready\n')
    while not shouldexit:
        signal.pause()
    if delayexit:
        time.sleep(delayexit)
    signal.signal(shouldexit[0], signal.SIG_DFL)
    os.kill(os.getpid(), shouldexit[0])
    raise RuntimeError("should've terminated due to %d" % shouldexit[0])

def signal_echoer(*signals, **kwargs):
    r, w = os.pipe()
    pid = echo_signals(w, signals, **kwargs)
    os.close(w)
    r = os.fdopen(r, 'r')
    assert r.readline() == 'ready\n'
    log.debug('signal_echoer {0} ready'.format(pid))
    return pid, r

import re
from functools import partial, wraps

def verifies_line(regex, verifier=None):
    if isinstance(regex, basestring):
        regex = re.compile(regex)
    if not verifier: return partial(verifies_line, regex)
    @wraps(verifier)
    def verify_line(f, *args):
        line = f.readline()
        log.debug('read line ' + repr(line))
        match = regex.match(line)
        assert match, \
            'expected line to match {0!r} got {1!r}'.format(regex, line)
        args += match.groups()
        return verifier(*args)
    return verify_line

@verifies_line(r'got (\d+)')
def verify_got_signal(i, sig, got):
    got = int(got)
    assert got == sig, \
        'got signal #{0} mismatch: expected {1} got {2}' \
        .format(i, sig, got)
    return got

@verifies_line(r'exiton (\d+)')
def verify_exiton_signal(i, sig, got):
    got = int(got)
    assert got == sig, \
        'exiton signal #{0} mismatch: expected {1} got {2}' \
        .format(i, sig, got)
    return got

def test_signal_echoer():
    # test the test before we test
    pid, r = signal_echoer(signal.SIGINT, signal.SIGTERM)
    for i, sig in  enumerate((signal.SIGTERM, signal.SIGINT)*2):
        os.kill(pid, sig)
        verify_got_signal(r, i, sig)
    os.kill(pid, signal.SIGKILL)
    gotpid, status = os.waitpid(pid, 0)
    assert pid == gotpid
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL

    pid, r = signal_echoer(signal.SIGINT, signal.SIGTERM, exiton={signal.SIGTERM})
    for i, sig in  enumerate((signal.SIGTERM, signal.SIGINT)*2):
        os.kill(pid, sig)
        if sig == signal.SIGTERM:
            verify_exiton_signal(r, i, sig)
            break
        verify_got_signal(r, i, sig)
    os.kill(pid, signal.SIGKILL)
    gotpid, status = os.waitpid(pid, 0)
    assert pid == gotpid
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGTERM

def test_killer():
    if reaper.theReaper is not None:
        reaper.theReaper.unhookup_sigchld()
        reaper.theReaper = None

    sigseq = lambda sigs: zip((None,) + (.01,)*(len(sigs)-1), sigs)
    seqs = [sigseq(filter(None, seq)) for seq in product(
        (None, signal.SIGHUP),  (None, signal.SIGHUP),
        (None, signal.SIGTERM), (None, signal.SIGTERM),
        (None, signal.SIGINT),  (None, signal.SIGINT),
        (signal.SIGKILL,))]
    for seq in [None] + seqs:
        log.debug('-- begin --')
        log.debug('seq: ' + repr(seq))
        pid, r = signal_echoer(signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
        q = Queue.Queue()
        k = killer.Killer(pid, sequence=seq, callback=q.put)
        if seq is None:
            seq = killer.Killer.sequence
        log.debug('k.sequence: ' + repr(k.sequence))
        for i, (delay, sig) in  enumerate(seq):
            if sig != signal.SIGKILL:
                got = verify_got_signal(r, i, sig)
                log.debug('verify_got {}'.format(got))
        obit = q.get()
        log.debug('q gotl ' + repr(obit))
        assert obit.pid == pid
        assert obit.exitstatus is None
        assert obit.termsig == signal.SIGKILL
        log.debug('-- end --')

    seq = sigseq((signal.SIGHUP,  signal.SIGHUP,
                  signal.SIGTERM, signal.SIGTERM,
                  signal.SIGINT,  signal.SIGINT,
                  signal.SIGKILL))
    for termsig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
        pid, r = signal_echoer(signal.SIGHUP, signal.SIGINT, signal.SIGTERM,
            exiton={termsig})
        q = Queue.Queue()
        k = killer.Killer(pid, sequence=seq, callback=q.put)
        if seq is None:
            seq = killer.Killer.sequence
        for i, (delay, sig) in  enumerate(seq):
            if sig != signal.SIGKILL:
                if sig == termsig:
                    verify_exiton_signal(r, i, sig)
                    break
                verify_got_signal(r, i, sig)
        obit = q.get()
        assert obit.pid == pid
        assert obit.exitstatus is None
        assert obit.termsig == termsig

import reaper

def test_killer_reaper():
    reaper.Reaper()

    pid, r = signal_echoer(signal.SIGTERM, signal.SIGINT,
        exiton={signal.SIGTERM, signal.SIGINT},
        delayexit=0.1)
    q = Queue.Queue()
    killtime = time.time()
    k = killer.Killer(pid, callback=q.put, sequence=(
        (None, signal.SIGTERM),
        (0.2,    signal.SIGKILL)))
    obit = q.get()
    verify_exiton_signal(r, 0, signal.SIGTERM)
    assert obit.termsig == signal.SIGTERM
    killtime = obit.waittime - killtime
    assert abs(killtime - 0.2) < 0.01

    reaper.theReaper = None

def test_killer_reaper_sigchld():
    reaper.Reaper().hookup_sigchld()

    pid, r = signal_echoer(signal.SIGTERM, signal.SIGINT,
        exiton={signal.SIGTERM, signal.SIGINT},
        delayexit=0.1)

    got = []
    killtime = time.time()
    k = killer.Killer(pid, callback=got.append, sequence=(
        (None, signal.SIGTERM),
        (0.2,  signal.SIGKILL)))
    while not got:
        signal.pause()
    obit = got.pop(0)

    verify_exiton_signal(r, 0, signal.SIGTERM)
    assert obit.termsig == signal.SIGTERM
    killtime = obit.waittime - killtime
    assert abs(killtime - 0.1) < 0.01

    reaper.theReaper.unhookup_sigchld()
    reaper.theReaper = None
