from __future__ import unicode_literals

import collections
import copy
import difflib
import inspect
import json
import os
import re
import sys
import unittest
import urlparse

class BaseError(object):
    pass

class UnexpectedKey(BaseError):
    pass

class KeyNotFound(BaseError):
    pass

class UnexpectedIndex(BaseError):
    pass

class IndexNotFound(BaseError):
    pass

class Difference(BaseError):
    def __init__(self, actual, expected):
        self.actual = actual
        self.expected = expected

    def split(self):
        convert = lambda x: getattr(x, '__name__', x)
        return convert(self.actual), convert(self.expected)

class RegexNotMatched(Difference):
    pass

class TypeNotMatched(Difference):
    pass

class MinNumberNotMatched(BaseError):
    def __init__(self, actual, expected, min_number):
        self.actual = actual
        self.expected = expected
        self.min_number = min_number

    def split(self):
        actual = self.actual + [IndexNotFound.__name__] * (self.min_number - len(self.actual))
        expected = self.expected + [self.expected[-1]] * (self.min_number - len(self.expected))
        return actual, expected


class Empty(object):
    """Placeholder for Empty objects."""
    pass


def prepare(actual, expected, sanitized_keys):
    """
        This function tries to sanitize actual and expected trees so that they can be processed by the differ.
        A few checks are performed on the expected tree to make sure it is valid.
        Both trees are processed with the following:
        - method is lowercased
        - headers keys are lowercased
        - headers keys are lowercased in matchingRules
        - query params are converted to a dict of lists

        The input trees are modified in place.
    """
    def apply_safe(function, x):
        try:
            return function(x)
        except:
            return x

    sanitize_empty_keys(actual, expected, sanitized_keys)

    for tree in (actual, expected):
        if 'method' in tree:
            tree['method'] = apply_safe(lambda x: x.lower(), tree['method'])
        if 'headers' in tree:
            tree['headers'] = apply_safe(
                lambda x: dict((k.lower(), format_header_value(v)) for k, v in x.items()),
                tree['headers'],
            )
        if 'matchingRules' in tree:
            lower_header = lambda x: x.lower() if x.startswith('$.headers') else x
            tree['matchingRules'] = apply_safe(
                lambda d: dict((lower_header(k), v) for k, v in d.items()),
                tree['matchingRules'],
            )
        if 'query' in tree:
            tree['query'] = apply_safe(
                lambda x: urlparse.parse_qs(x, keep_blank_values=True),
                tree['query'],
            )


def sanitize_empty_keys(actual, expected, keys):
    for key in keys:
        expected_value, actual_value = expected.get(key, Empty), actual.get(key, Empty)
        if expected_value is Empty:
            actual.pop(key, None)  # No check at all if key is not in expected
        elif actual_value in (None, Empty) and expected_value is None:
            actual[key] = None


def format_header_value(header_value):
    return ','.join(value.strip(' ') for value in header_value.split(','))


def walk_and_assert(actual, expected, rules=None, paths=None, ignore_extra_keys=True):
    paths = paths or ('$.',)
    rules = rules or {}
    diff_tree = None

    checked_rules = [rules[path] for path in paths if path in rules]
    for rule in checked_rules:
        diff = check_rule(rule, actual, expected)
        if diff:
            return diff

    if type(expected) == dict:
        if not isinstance(actual, collections.Mapping):
            return TypeNotMatched(actual, expected)

        diff_tree = {}
        next_paths = tuple('%s.*' % path for path in paths)
        for key, expected_value in expected.items():
            if key not in actual:
                diff_tree[key] = Difference(KeyNotFound, expected_value)
            else:
                actual_value = actual[key]
                diff_tree[key] = walk_and_assert(
                    actual_value,
                    expected_value,
                    rules=rules,
                    paths=(
                        next_paths +
                        tuple('%s.%s' % (path, key) for path in paths) +  # dot notation
                        tuple("%s['%s']" % (path, key) for path in paths)  # bracket notation
                    ),
                    ignore_extra_keys=ignore_extra_keys,
                )
        if not ignore_extra_keys:
            unexpected_keys = set(actual.keys()) - set(expected.keys())
            for key in unexpected_keys:
                diff_tree[key] = Difference(actual[key], UnexpectedKey)

    elif type(expected) in (list, tuple, set):  # Do not use collections.Sequence, it also matches strings
        if not isinstance(actual, list):
            return TypeNotMatched(actual, expected)

        diff_tree = []
        next_paths = tuple('%s[*]' % path for path in paths)
        for i, expected_value in enumerate(expected):
            if i >= len(actual):
                diff_tree.append(Difference(IndexNotFound, expected_value))
            else:
                actual_value = actual[i]
                diff_tree.append(walk_and_assert(
                    actual_value,
                    expected_value,
                    rules=rules,
                    paths=next_paths + tuple('%s[%s]' % (path, i) for path in paths),
                    ignore_extra_keys=ignore_extra_keys,
                ))
        for i, actual_value in enumerate(actual[len(expected):], len(expected)):
            diff_tree.append(walk_and_assert(
                actual_value,
                expected[0],  # use expected_value[0] as default: is this what we want? When do we UnexpectedIndex()?
                rules=rules,
                paths=next_paths + tuple('%s[%s]' % (path, i) for path in paths),
                ignore_extra_keys=ignore_extra_keys
            ))

    else:
        if not checked_rules and actual != expected:
            # no rule matching => default to literal matching
            diff_tree = Difference(actual, expected)
        else:
            diff_tree = actual

    return diff_tree


def check_rule(rule, actual, expected):
    if not rule:
        return

    match = rule.get('match')
    if match == 'type':
        if type(actual) != type(expected):
            return TypeNotMatched(actual, expected)
    elif match == 'regex':
        regex = rule['regex']
        if not re.match(regex, actual):
            return RegexNotMatched(actual, regex)

    min_number = rule.get('min')
    if min_number:
        if len(actual) < min_number:
            return MinNumberNotMatched(actual, expected, min_number)


def build_trees_from_diff(diff, errors):
    if type(diff) == dict:
        actual, expected = {}, {}
        for key, value in diff.items():
            actual_next, expected_next = build_trees_from_diff(value, errors)
            actual[key] = actual_next
            expected[key] = expected_next
    elif type(diff) in (list, tuple, set):
        actual, expected = [], []
        for el in diff:
            actual_next, expected_next = build_trees_from_diff(el, errors)
            actual.append(actual_next)
            expected.append(expected_next)
    else:
        if isinstance(diff, BaseError):
            errors.append(diff)
            actual, expected = diff.split()
        else:
            actual, expected = diff, diff
    return actual, expected


def request_checker(actual, expected):
    prepare(actual, expected, sanitized_keys=('headers', 'query', 'body'))
    rules = expected.pop('matchingRules', {})
    ignore_extra_keys = ('headers',)
    diff_tree = {}
    for key in ('method', 'path', 'query', 'headers', 'body'):
        diff_tree[key] = walk_and_assert(
            actual.get(key, None),
            expected.get(key, None),
            rules=rules,
            paths=('$.%s' % key,),
            ignore_extra_keys=key in ignore_extra_keys,
        )

    errors = []
    tree1, tree2 = build_trees_from_diff(diff_tree, errors)
    format_diff(tree1, tree2)
    return not errors


def response_checker(actual, expected):
    prepare(actual, expected, sanitized_keys=('headers', 'status', 'body'))
    rules = expected.pop('matchingRules', {})
    ignore_extra_keys = ('headers', 'body')
    diff_tree = {}
    for key in ('status', 'headers', 'body'):
        diff_tree[key] = walk_and_assert(
            actual.get(key, None),
            expected.get(key, None),
            rules=rules,
            paths=('$.%s' % key,),
            ignore_extra_keys=key in ignore_extra_keys,
        )

    errors = []
    tree1, tree2 = build_trees_from_diff(diff_tree, errors)
    format_diff(tree1, tree2)
    return not errors


def format_diff(tree1, tree2):
    def prettify(x):
        added_re = re.compile('^([+] [^\n]*)\n$')
        removed_re = re.compile('^([-] [^\n]*)\n$')
        ret = re.sub(added_re, r'\033[1;32m\1\n\033[0;m', x)
        if ret == x:
            ret = re.sub(removed_re, r'\033[1;31m\1\n\033[0;m', x)
        return ret
    keepends = True
    lines = difflib.unified_diff(
        (json.dumps(tree1, sort_keys=True, indent=4) + '\n').splitlines(keepends),
        (json.dumps(tree2, sort_keys=True, indent=4) + '\n').splitlines(keepends),
    )
    sys.stdout.writelines([prettify(line) for line in lines])


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
