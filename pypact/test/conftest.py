import os
import sys


def get_testcases(version):
    path = os.path.split(__file__)[0]
    path = '%s/pact_specification/v%s/testcases' % (path, version)
    return [
        os.path.join(root, file_)
        for root, _dirs, files in os.walk(path)
        for file_ in files if file_.split('.')[-1] == 'json'
    ]

def pytest_generate_tests(metafunc):
    if 'testcase_v1_1' in metafunc.fixturenames:
        metafunc.parametrize("testcase_v1_1", get_testcases('1.1'))
    if 'testcase_v2' in metafunc.fixturenames:
        metafunc.parametrize("testcase_v2", get_testcases('2'))
