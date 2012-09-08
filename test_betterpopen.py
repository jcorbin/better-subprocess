import os
import resource
import signal
import subprocess
import time

from betterpopen import Popen, TEMPFILE

def test_wait():
    proc = Popen('false')
    assert proc.wait() == 1
    assert proc.rusage is not None

def test_poll():
    proc = Popen('gzip -c /dev/urandom', stdout=open('/dev/null', 'w'))
    assert proc.rusage is None

    assert proc.poll() is None
    assert proc.rusage is None

    time.sleep(.05)
    proc.terminate()

    assert proc.wait() == -signal.SIGTERM
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

def test_context():
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

def file_read_size(f, bufsize=4096):
    size = 0
    while True:
        buf = f.read(bufsize)
        if not buf: break
        size += len(buf)
    return size

def test_tempfile():
    is_positive = lambda size: size  > 0
    is_zero     = lambda size: size == 0
    for command, returncode, stdout_size, stderr_size in (
        ('ls /tmp', 0, is_positive, is_zero),
        ('ls /__path__/to/nowhere', 2, is_zero, is_positive)):
        stdout_path = stderr_path = None
        with Popen(command, stdout=TEMPFILE, stderr=TEMPFILE,
                expected_exitcodes={returncode}) as proc:
            stdout_path = proc.stdout.name
            stderr_path = proc.stderr.name
            assert os.path.exists(stdout_path)
            assert os.path.exists(stderr_path)
            assert proc.wait() == returncode
            stdout_temp_size = os.path.getsize(stdout_path)
            stderr_temp_size = os.path.getsize(stderr_path)
            assert stdout_size(stdout_temp_size)
            assert stderr_size(stderr_temp_size)
            assert stdout_temp_size == file_read_size(proc.stdout)
            assert stderr_temp_size == file_read_size(proc.stderr)
        del proc
        assert not os.path.exists(stdout_path)
        assert not os.path.exists(stderr_path)
