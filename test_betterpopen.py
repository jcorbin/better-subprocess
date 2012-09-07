import resource
import signal

from betterpopen import Popen

proc = Popen('false')
assert proc.wait() == 1
assert proc.rusage is not None

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
