import os
import sys
from functools import wraps

def fork_run(run, *args, **kwargs):
    pid = os.fork()
    if pid == 0:
        run(*args, **kwargs)
        sys.exit(255)
    return pid

def forks(f):
    @wraps(f)
    def forker(*args, **kwargs):
        return fork_run(f, *args, **kwargs)
    return forker
