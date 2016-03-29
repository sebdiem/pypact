from __future__ import unicode_literals

import collections
import copy
import json
import os
import re
import sys
import unittest
import urlparse


class Empty(object):
    """Placeholder for Empty objects."""
    pass


def get_key(d, key):
    return d.get(key, Empty)


def format_header_value(header_value):
    return ','.join(value.strip(' ') for value in header_value.split(','))


def check_headers(actual, expected, matching_rules):
    if actual is None or actual is Empty:
        return expected is None or expected is Empty

    if expected is Empty:
        return True

    expected = dict((k.lower(), format_header_value(v)) for (k, v) in expected.items())
    actual = dict((k.lower(), format_header_value(v)) for (k, v) in actual.items() if k.lower() in expected)

    prefix = '$.headers'
    matching_rules = dict((k[len(prefix):].lower(), v) for k, v in matching_rules.items() if k.startswith(prefix))

    try:
        walk_and_assert(actual, expected, rules=matching_rules, ignore_extra_keys=True)
    except AssertionError:
        return False
    return True


def check_request_query(actual, expected):
    if actual is None or actual is Empty:
        return expected is None or expected is Empty

    if expected is Empty:
        return True

    actual = urlparse.parse_qs(actual, keep_blank_values=True)
    expected = urlparse.parse_qs(expected, keep_blank_values=True)

    return actual == expected


def check_body(actual, expected, matching_rules, ignore_extra_keys):
    if actual is None or actual is Empty:
        return expected is None or expected is Empty

    if expected is Empty:
        return True

    prefix = '$.body'
    matching_rules = dict((k[len(prefix):], v) for k, v in matching_rules.items() if k.startswith(prefix))

    try:
        walk_and_assert(actual, expected, rules=matching_rules, ignore_extra_keys=ignore_extra_keys)
    except AssertionError:
        return False
    return True


def check_rule(rule, actual, expected):
    if not rule:
        return

    match = rule.get('match')
    if match == 'type':
        assert type(actual) == type(expected)
    elif match == 'regex':
        regex = rule.get('regex')
        assert regex
        assert re.match(regex, actual)

    min_number = rule.get('min')
    if min_number:
        assert len(actual) >= min_number


def walk_and_assert(actual, expected, rules=None, roots=None, ignore_extra_keys=True):
    roots = roots or ('',)
    rules = rules or {}
    print next(root for root in roots if '*' not in root)

    checked_rules = [rules[root] for root in roots if root in rules]
    for rule in checked_rules:
        check_rule(rule, actual, expected)

    if type(expected) == dict:
        assert isinstance(actual, collections.Mapping)
        next_roots = tuple('%s.*' % root for root in roots)
        for key, expected_value in expected.items():
            actual_value = actual.get(key, Empty)
            walk_and_assert(
                actual_value,
                expected_value,
                rules=rules,
                roots=(
                    next_roots +
                    tuple('%s.%s' % (root, key) for root in roots) +  # dot notation
                    tuple("%s['%s']" % (root, key) for root in roots)  # bracket notation
                ),
                ignore_extra_keys=ignore_extra_keys,
            )
        if not ignore_extra_keys:
            assert set(actual.keys()) == set(expected.keys())
    elif type(expected) == list:  # Do not use collections.Sequence, it also matches strings
        next_roots = tuple('%s[*]' % root for root in roots)
        for i, expected_value in enumerate(expected):
            assert i < len(actual)
            walk_and_assert(
                actual[i],
                expected_value,
                rules=rules,
                roots=next_roots + tuple('%s[%s]' % (root, i) for root in roots),
                ignore_extra_keys=ignore_extra_keys
            )
        for i, actual_value in enumerate(actual[len(expected):], len(expected)):
            walk_and_assert(
                actual[i],
                expected[0],  # use expected_value[0] as default: is this what we want?
                rules=rules,
                roots=next_roots + tuple('%s[%s]' % (root, i) for root in roots),
                ignore_extra_keys=ignore_extra_keys
            )
    elif not checked_rules:
        # no rule matching => default to literal matching
        assert actual == expected


def request_checker(actual, expected):
    try:
        assert actual['method'].lower() == expected['method'].lower()
        assert actual['path'] == expected['path']
        assert check_request_query(get_key(actual, 'query'), get_key(expected, 'query'))
        assert check_headers(
            get_key(actual, 'headers'),
            get_key(expected, 'headers'),
            expected.get('matchingRules', {}),
        )
        assert check_body(
            get_key(actual, 'body'),
            get_key(expected, 'body'),
            matching_rules=expected.get('matchingRules', {}),
            ignore_extra_keys=False,
        )
    except AssertionError:
        return False
    return True


def response_checker(actual, expected):
    try:
        assert get_key(actual, 'status') == get_key(expected, 'status')
        assert check_headers(
            get_key(actual, 'headers'),
            get_key(expected, 'headers'),
            expected.get('matchingRules', {}),
        )
        assert check_body(
            get_key(actual, 'body'),
            get_key(expected, 'body'),
            matching_rules=expected.get('matchingRules', {}),
            ignore_extra_keys=True,
        )
    except AssertionError:
        return False
    return True


def check_file(file_, checker):
    with open(file_, 'r') as test_case:
        test_case = test_case.read()
        # one file contains strange chars and needs pre-treatment:
        test_case = test_case[test_case.find(b'{'):]
        test_case = json.loads(test_case)
    msg = '%s: %s' % (file_, test_case['comment'])
    success = True
    if test_case['match'] != checker(test_case['actual'], test_case['expected']):
        msg += '...Failed'
        success = False
    else:
        msg += '...OK'
    print msg
    return success


if __name__ == '__main__':
    failed = {'request': 0, 'response': 0}
    path = sys.argv[1] if len(sys.argv) > 1 else None
    if path:
        request_or_response = 'request' if os.path.join('testcases', 'request') in path else 'response'
        checker = {'request': request_checker, 'response': response_checker}[request_or_response]
        check_file(path, checker)
        sys.exit(0)
    for root, dirs, files in os.walk('testcases'):
        for file_ in files:
            if file_.split('.')[-1] == 'json':
                path = os.path.join(root, file_)
                request_or_response = 'request' if os.path.join('testcases', 'request') in path else 'response'
                checker = {'request': request_checker, 'response': response_checker}[request_or_response]
                if not check_file(path, checker):
                    failed[request_or_response] += 1
    if any(failed.values()):
        for k, v in failed.items():
            print '%s %ss failed' % (v, k)
    else:
        print 'Success'
