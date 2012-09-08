import os
import signal
import sys

from test_util import forks

@forks
def echo_signals(w, signals):
    def handler(signum, frame):
        os.write(w, '%d\n' % signum)
    for sig in signals:
        signal.signal(sig, handler)
    os.write(w, 'ready\n')
    while True:
        signal.pause()
    sys.exit(0)

def signal_echoer(*signals):
    r, w = os.pipe()
    pid = echo_signals(w, signals)
    os.close(w)
    r = os.fdopen(r, 'r')
    assert r.readline() == 'ready\n'
    return pid, r

def verify_got_signal(i, r, sig):
    line = r.readline().strip()
    got = int(line) if line else None
    assert got == sig, \
        'signal #{0} mismatch: {1}(got) vs {2}(expected)' \
        .format(i, got, sig)

def test_signal_echoer():
    # test the test before we test
    pid, r = signal_echoer(signal.SIGINT, signal.SIGTERM)
    for i, sig in  enumerate((signal.SIGTERM, signal.SIGINT)*2):
        os.kill(pid, sig)
        verify_got_signal(i, r, sig)
    os.kill(pid, signal.SIGKILL)
    gotpid, status = os.waitpid(pid, 0)
    assert pid == gotpid
    assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL

test_signal_echoer()

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(process)d.%(thread)d] %(name)s %(levelname)s %(message)s')

import reaper
reaper.log.setLevel(logging.DEBUG)

import killer
killer.log.setLevel(logging.DEBUG)
from itertools import product
import Queue

def test_killer():
    sigseq = lambda sigs: zip((None,) + (.01,)*(len(sigs)-1), sigs)
    seqs = [sigseq(filter(None, seq)) for seq in product(
        (None, signal.SIGHUP),  # (None, signal.SIGHUP),
        (None, signal.SIGTERM), (None, signal.SIGTERM),
        (None, signal.SIGINT),  (None, signal.SIGINT),
        (signal.SIGKILL,))]
    for seq in [None] + seqs:
        pid, r = signal_echoer(signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
        q = Queue.Queue()
        k = killer.Killer(pid, sequence=seq, callback=q.put)
        for i, (delay, sig) in  enumerate(k.sequence):
            if sig != signal.SIGKILL:
                verify_got_signal(i, r, sig)
        obit = q.get()
        print obit
        assert obit.pid == pid
        assert obit.returncode is None
        assert obit.termsig == signal.SIGKILL

test_killer()

# TODO: killer + reaper
# TODO: killer + reaper w/ SIGCLD
