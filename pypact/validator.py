from __future__ import unicode_literals

import collections
import copy
import json
import os
import re
import sys
import unittest
import urlparse

class BaseError(object):
    def __repr__(self):
        return self.__class__.__name__

class Difference(BaseError):
    def __init__(self, actual, expected):
        self.actual = actual
        self.expected = expected

    def __repr__(self):
        return '%s("expected %s, got %s")' % (self.__class__.__name__, repr(self.expected), repr(self.actual))

class RegexNotMatched(Difference):
    pass

class MinNumberNotMatched(Difference):
    pass

class UnexpectedKey(BaseError):
    def __init__(self, key):
        self.key = key

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.key))

class KeyNotFound(UnexpectedKey):
    pass

class UnexpectedIndex(UnexpectedKey):
    pass

class IndexNotFound(BaseError):
    def __init__(self, actual, expected):
        self.actual = actual + [self.__class__] * (len(expected) - len(actual))
        self.expected = expected

    def __repr__(self):
        return '%s("expected %s, got %s")' % (self.__class__.__name__, repr(self.expected), repr(self.actual))


class Empty(object):
    """Placeholder for Empty BaseErrors."""
    pass


def get_key(d, key):
    return d.get(key, Empty)


def format_header_value(header_value):
    return ','.join(value.strip(' ') for value in header_value.split(','))


def simple_check(path, actual, expected, prepare_function=lambda x: x):
    errors = []
    if prepare_function(actual) != prepare_function(expected):
        errors.append((path, Difference(actual, expected)))
    return errors


def check_headers(actual, expected, matching_rules):
    errors = []
    path = '$.headers'
    if actual is None or actual is Empty:
        if expected is not None and expected is not Empty:
            errors.append((path, Difference(actual, expected)))

    elif expected is not Empty:
        expected = dict((k.lower(), format_header_value(v)) for (k, v) in expected.items())
        actual = dict((k.lower(), format_header_value(v)) for (k, v) in actual.items() if k.lower() in expected)

        matching_rules = dict((k.lower(), v) for k, v in matching_rules.items() if k.startswith(path))

        errors.extend(walk_and_assert(actual, expected, paths=(path,), rules=matching_rules, ignore_extra_keys=True))

    return errors


def check_request_query(actual, expected):
    errors = []
    path = '$.query'
    if actual is None or actual is Empty:
        if expected is not None and expected is not Empty:
            errors.append((path, Difference(actual, expected)))

    elif expected is not Empty:
        actual = urlparse.parse_qs(actual, keep_blank_values=True)
        expected = urlparse.parse_qs(expected, keep_blank_values=True)
        errors.extend(walk_and_assert(actual, expected, paths=(path,), ignore_extra_keys=False))

    return errors


def check_body(actual, expected, matching_rules, ignore_extra_keys):
    errors = []
    path = '$.body'
    if actual is None or actual is Empty:
        if expected is not None and expected is not Empty:
            errors.append((path, Difference(actual, expected)))

    elif expected is not Empty:
        matching_rules = dict((k, v) for k, v in matching_rules.items() if k.startswith(path))
        errors.extend(
            walk_and_assert(actual, expected, paths=(path,), rules=matching_rules, ignore_extra_keys=ignore_extra_keys)
        )

    return errors


def check_rule(rule, actual, expected, path):
    if not rule:
        return

    errors = []
    match = rule.get('match')
    if match == 'type':
        if type(actual) != type(expected):
            errors.append((path, Difference(type(actual), type(expected))))
    elif match == 'regex':
        regex = rule['regex']
        if not re.match(regex, actual):
            errors.append((path, RegexNotMatched(actual, regex)))

    min_number = rule.get('min')
    if min_number:
        if len(actual) < min_number:
            errors.append((path, MinNumberNotMatched(len(actual), min_number)))
    return errors


def walk_and_assert(actual, expected, rules=None, paths=None, ignore_extra_keys=True):
    paths = paths or ('',)
    rules = rules or {}
    errors = []
    explicit_path = next(path for path in paths if '*' not in path)

    checked_rules = [rules[path] for path in paths if path in rules]
    for rule in checked_rules:
        errors.extend(check_rule(rule, actual, expected, explicit_path))

    if type(expected) == dict:
        if not isinstance(actual, collections.Mapping):
            errors.append(Difference(actual, expected))
        else:
            next_paths = tuple('%s.*' % path for path in paths)
            for key, expected_value in expected.items():
                if key not in actual:
                    errors.append((explicit_path, KeyNotFound(key)))
                else:
                    actual_value = actual[key]
                    errors.extend(walk_and_assert(
                        actual_value,
                        expected_value,
                        rules=rules,
                        paths=(
                            next_paths +
                            tuple('%s.%s' % (path, key) for path in paths) +  # dot notation
                            tuple("%s['%s']" % (path, key) for path in paths)  # bracket notation
                        ),
                        ignore_extra_keys=ignore_extra_keys,
                    ))
            if not ignore_extra_keys:
                unexpected_key = set(actual.keys()) - set(expected.keys())
                errors.extend([(explicit_path, UnexpectedKey(key)) for key in unexpected_key])

    elif type(expected) == list:  # Do not use collections.Sequence, it also matches strings
        next_paths = tuple('%s[*]' % path for path in paths)
        if len(actual) < len(expected):
            errors.append((explicit_path, IndexNotFound(actual, expected)))
        for i, expected_value in enumerate(expected):
            if i < len(actual):
                errors.extend(walk_and_assert(
                    actual[i],
                    expected_value,
                    rules=rules,
                    paths=next_paths + tuple('%s[%s]' % (path, i) for path in paths),
                    ignore_extra_keys=ignore_extra_keys
                ))
        for i, actual_value in enumerate(actual[len(expected):], len(expected)):
            errors.extend(walk_and_assert(
                actual[i],
                expected[0],  # use expected_value[0] as default: is this what we want? We need UnexpectedIndex()
                rules=rules,
                paths=next_paths + tuple('%s[%s]' % (path, i) for path in paths),
                ignore_extra_keys=ignore_extra_keys
            ))

    elif not checked_rules:
        # no rule matching => default to literal matching
        if actual != expected:
            errors.append((explicit_path, Difference(actual, expected)))

    return errors


def request_checker(actual, expected):
    errors = []
    errors.extend(simple_check('$.method', actual['method'], expected['method'], lambda x: x.lower()))
    errors.extend(simple_check('$.path', actual['path'], expected['path']))
    errors.extend(check_request_query(get_key(actual, 'query'), get_key(expected, 'query')))
    errors.extend(
        check_headers(
            get_key(actual, 'headers'),
            get_key(expected, 'headers'),
            expected.get('matchingRules', {}),
        )
    )
    errors.extend(
        check_body(
            get_key(actual, 'body'),
            get_key(expected, 'body'),
            matching_rules=expected.get('matchingRules', {}),
            ignore_extra_keys=False,
        )
    )
    if errors:
        print errors
        return False
    return True


def response_checker(actual, expected):
    errors = []
    errors.extend(simple_check('$.status', get_key(actual, 'status'), get_key(expected, 'status')))
    errors.extend(
        check_headers(
            get_key(actual, 'headers'),
            get_key(expected, 'headers'),
            expected.get('matchingRules', {}),
        )
    )
    errors.extend(
        check_body(
            get_key(actual, 'body'),
            get_key(expected, 'body'),
            matching_rules=expected.get('matchingRules', {}),
            ignore_extra_keys=True,
        )
    )
    if errors:
        print errors
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
    for root, dirs, files in os.walk('/Users/Seb/temp/pact-specification/testcases'):
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
