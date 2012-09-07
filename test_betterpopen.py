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

def text_context():
    with Popen('ls /',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE) as proc:
        assert len(proc.stdout.read())
        assert not len(proc.stderr.read())

    try:
        with Popen('ls /__path__/to/nowhere',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE) as proc:
            assert not len(proc.stdout.read())
            assert len(proc.stderr.read())
    except CalledProcessError:
        pass
    else:
        assert False, "shoud've raised subprocess.CalledProcessError"


    with Popen('ls /__path__/to/nowhere',
            expected_exitcodes={2},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE) as proc:
        assert not len(proc.stdout.read())
        assert len(proc.stderr.read())
