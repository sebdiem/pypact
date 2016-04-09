import json
import os

import pytest

from ..validator import compare_requests, compare_responses


def spec_test(testcase):
    with open(testcase, 'r') as test_case:
        test_case = test_case.read()
        test_case = json.loads(test_case)
    compare = compare_requests if os.path.join('testcases', 'request') in testcase else compare_responses
    diff = list(compare(test_case['actual'], test_case['expected']))
    if test_case['match'] and diff:
        raise AssertionError(''.join(['\nfile %s:\n' % testcase] + diff))
    if not test_case['match'] and not diff:
        raise AssertionError('file "%s": actual and expected should not match but no diff detected' % testcase)


def test_specification_v1_1(testcase_v1_1):
    spec_test(testcase_v1_1)


def test_specification_v2(testcase_v2):
    spec_test(testcase_v2)


def test_diff_formatter():
    pass
