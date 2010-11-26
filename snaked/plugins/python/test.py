import os
import multiprocessing
import time

def test_runner(conn, cwd, match, files):
    import pytest
    os.chdir(cwd)

    args = ' '.join(['-q', ('-k %s' % match) if match else ''] + files)
    pytest.main(args, plugins=[Collector(conn)])

def run_test(project_dir, match=None, files=[]):
    conn, inconn = multiprocessing.Pipe()
    proc = multiprocessing.Process(target=test_runner, args=(inconn, project_dir, match, files))
    proc.start()

    return proc, conn


class Collector(object):
    def __init__(self, conn):
        self.conn = conn
        self._durations = {}

    def pytest_runtest_logreport(self, report):
        """:type report: _pytest.runner.TestReport()"""

        if report.passed:
            self.conn.send(('PASS', report.nodeid))
        elif report.failed:
            if report.when != "call":
                self.conn.send(('ERROR', report.nodeid, str(report.longrepr)))
            else:
                self.conn.send(('FAIL', report.nodeid, str(report.longrepr)))
        elif report.skipped:
            self.conn.send(('SKIP', report.nodeid))

    def pytest_runtest_call(self, item, __multicall__):
        names = tuple(item.listnames())
        start = time.time()
        try:
            return __multicall__.execute()
        finally:
            self._durations[names] = time.time() - start

    def get_parents(self, node):
        while True:
            parent = node.parent
            if parent:
                yield parent.name
                node = parent
            else:
                break

    def pytest_collectreport(self, report):
        """:type report: _pytest.runner.CollectReport()"""
        if report.passed:
            for node in report.result:
                self.conn.send(('COLLECT',
                    node.name if report.nodeid == '.' else (report.nodeid + '::' + node.name)))
        elif report.failed:
            self.conn.send(('FAILED_COLLECT', report.nodeid, str(report.longrepr)))

    def pytest_internalerror(self, excrepr):
        self.conn.send(('INTERNAL_ERROR', excrepr))

    def pytest_sessionstart(self, session):
        self.suite_start_time = time.time()

    def pytest_sessionfinish(self, session, exitstatus, __multicall__):
        self.conn.send(('END', ))
