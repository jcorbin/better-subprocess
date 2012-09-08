import os
from collections import namedtuple

class obituary(namedtuple('obituary', 'waittime pid status rusage')):
    """
    Describes a process death.  The waittime field is the time when os.wait4
    was called.  The pid, status, and rusage fields are as returned by
    os.wait4.
    """
    @property
    def exitstatus(self):
        if os.WIFEXITED(self.status):
            return os.WEXITSTATUS(self.status)

    @property
    def termsig(self):
        if os.WIFSIGNALED(self.status):
            return os.WTERMSIG(self.status)

    @property
    def stopsig(self):
        if os.WIFSTOPPED(self.status):
            return os.WSTOPSIG(self.status)

    @property
    def coredump(self):
        return os.WCOREDUMP(self.status)
