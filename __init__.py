from betterpopen import Popen
from killer import Killer
from obituary import obituary
from reaper import Reaper, AsyncReaper, ProcessRegistry

import signal


def as_exited(procs, limit=40):
    pending = []
    while True:
        still = []
        for proc in pending:
            if proc.returncode is not None:
                yield proc
            else:
                still.append(proc)
        pending = still
        while len(pending) < limit and procs is not None:
            try:
                proc = next(procs)
            except StopIteration:
                procs = None
            else:
                if proc.returncode:
                    yield proc
                else:
                    pending.append(proc)
        if not len(pending):
            break
        signal.pause()
