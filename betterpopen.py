#!/usr/bin/env python

import collections
import errno
import os
from Queue import Queue
import resource
import signal
import time
import shlex
import subprocess
import tempfile

import reaper

import logging
log = logging.getLogger(__name__)

def compose(f, g):
    def h():
        f()
        g()
    return h

TEMPFILE = -3

class Popen(subprocess.Popen):
    registry = reaper.ProcessRegistry()

    expected_exitcodes = {0}
    temp_maker = staticmethod(tempfile.mkstemp)

    def __init__(self, command, *args, **kwargs):
        for key in ('expected_exitcodes', 'temp_maker'):
            try:
                setattr(self, key, kwargs.pop(key))
            except KeyError:
                pass

        self.rusage = None
        self.exectime = None
        self.waittime = None

        rlimits = kwargs.pop('rlimits', ())
        if isinstance(rlimits, collections.Mapping):
            rlimits = rlimits.iteritems()
        self.rlimits = tuple(rlimits)
        if self.rlimits:
            try:
                kwargs['preexec_fn'] = compose(
                    kwargs['preexec_fn'], self._setrlimits)
            except KeyError:
                kwargs['preexec_fn'] = self._setrlimits

        if isinstance(command, basestring):
            self.commandstr = command
            command = shlex.split(command)
        else:
            self.commandstr = subprocess.list2cmdline(command)
        self.command = command

        super(Popen, self).__init__(command, *args, **kwargs)

    def _tempfile(self):
        w, name = self.temp_maker()
        r = os.open(name, os.O_RDONLY)
        self._set_cloexec_flag(w)
        # TODO: bufsize?
        r = open(name, 'rU' if self.universal_newlines else 'rb', 0)
        r = tempfile._TemporaryFileWrapper(r, name)
        self._set_cloexec_flag(r.fileno())
        return r, w

    def _get_handles(self, stdin, stdout, stderr):
        c2pwrite = errwrite = None

        if stdout == TEMPFILE:
            self.stdout, c2pwrite = self._tempfile()
            stdout = None

        if stderr == TEMPFILE:
            self.stderr, errwrite = self._tempfile()
            stderr = None

        return tuple(ai if ai is not None else bi for ai, bi in zip(
                (None, None, None, c2pwrite, None, errwrite),
                super(Popen, self)._get_handles(stdin, stdout, stderr)))

    def _execute_child(self, *args):
        self.exectime = time.time()
        super(Popen, self)._execute_child(*args)
        self.registry[self.pid] = self

    def _handle_obituary(self, obit):
        assert obit.pid == self.pid
        self.waittime = obit.waittime
        self.rusage = obit.rusage
        self._handle_exitstatus(obit.status)

    def _setrlimits(self):
        for r, limit in self.rlimits:
            resource.setrlimit(r, limit)

    def wait(self):
        """Wait for child process to terminate and records resource
        usage.  Returns returncode attribute."""
        if self.returncode is None:
            try:
                pid, sts, self.rusage = os.wait4(self.pid, 0)
                self.waittime = time.time()
            except OSError as e:
                if e.errno == errno.EINTR:
                    # interrupted by signal handler, and it did the wait for us
                    if self.returncode is not None:
                        sts = None
                elif e.errno != errno.ECHILD:
                    # This happens if SIGCLD is set to be ignored or waiting
                    # for child processes has otherwise been disabled for our
                    # process.  This child is dead, we can't get the status.
                    sts = 0
                else:
                    raise
            if sts is not None:
                self._handle_exitstatus(sts)
            try:
                del self.registry[self.pid]
            except KeyError:
                pass
        return self.returncode

    def check(self, expected_exitcodes=None):
        if expected_exitcodes is None:
            expected_exitcodes = self.expected_exitcodes
        retcode = self.wait()
        if retcode not in expected_exitcodes:
            raise subprocess.CalledProcessError(retcode, self.command)
        return retcode

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        retcode = self.wait()
        if retcode not in self.expected_exitcodes:
            err = subprocess.CalledProcessError(retcode, self.command)
            if exc_type is None:
                raise err
            else:
                log.error(str(err))
