The idea is to add features to subprocess which I usually find lacking:
* better default handling of string command using shlex module
* collect rusage data with os.wait4
* easier and more flexible check-calling
* support for reaping with SIGCLD

