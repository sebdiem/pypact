import copy
import json
import os

import pytest

from ..validator import compare_requests, compare_responses, format_diff


def spec_test(testcase):
    with open(testcase, 'r') as test_case:
        test_case = json.load(test_case)
    compare = compare_requests if os.path.join('testcases', 'request') in testcase else compare_responses
    diff = list(compare(test_case['actual'], test_case['expected']))
    if test_case['match'] and diff:
        raise AssertionError(''.join(
            ['\nfile %s: actual and expected should match but the compare function returned a diff\n' % testcase] + diff
        ))
    if not test_case['match'] and not diff:
        raise AssertionError(
            '\nfile "%s": actual and expected should not match but the compare function returned no diff' % testcase)


def test_specification_v1_1(testcase_v1_1):
    spec_test(testcase_v1_1)


def test_specification_v2(testcase_v2):
    spec_test(testcase_v2)


def test_diff_formatter():
    actual = {
        'toto': [
            {
                'id1': 1,
                'id2': 2,
                'id3': 3,
            },
            {}
        ]
    }
    expected = copy.deepcopy(actual)
    assert list(format_diff(actual, expected)) == []

    actual = {'toto': 1}
    expected = {'toto': 2}
    assert list(format_diff(actual, expected)) == [
        '--- actual\n',
        '+++ expected\n',
        '@@ -1,3 +1,3 @@\n',
        ' {\n',
        '\x1b[1;31m-    "toto": 1\n\x1b[0;m',
        '\x1b[1;32m+    "toto": 2\n\x1b[0;m',
        ' }\n',
    ]

    expected = {}
    assert list(format_diff(actual, expected)) == [
        '--- actual\n',
        '+++ expected\n',
        '@@ -1,3 +1 @@\n',
        '\x1b[1;31m-{\n\x1b[0;m',
        '\x1b[1;31m-    "toto": 1\n\x1b[0;m',
        '\x1b[1;31m-}\n\x1b[0;m',
        '\x1b[1;32m+{}\n\x1b[0;m',
    ]
