import resource
import signal
import subprocess

from betterpopen import Popen

def test_wait():
    proc = Popen('false')
    assert proc.wait() == 1
    assert proc.rusage is not None

def test_check():
    assert Popen('true').check() == 0
    assert Popen('false').check({1}) == 1

    try:
        Popen('false').check()
    except subprocess.CalledProcessError:
        pass
    else:
        assert False, "shoud've raised subprocess.CalledProcessError"

def test_rlimits():
    assert Popen('gzip -c /dev/urandom',
        stdout=open('/dev/null', 'w'),
        rlimits={
            resource.RLIMIT_CPU: (2, 4),
        }
    ).wait() == -signal.SIGXCPU

    assert Popen('gzip -c /dev/urandom',
        stdout=open('/dev/null', 'w'),
        rlimits={
            resource.RLIMIT_CPU: (2, 2),
        }
    ).wait() == -signal.SIGKILL
