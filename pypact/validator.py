# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import difflib
import json
import os
import re
import sys
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
        default_value = self.expected[-1] if self.expected else UnexpectedIndex
        expected = self.expected + [default_value] * (self.min_number - len(self.expected))
        return actual, expected


class Empty(object):
    """Placeholder for Empty objects."""
    pass


def prepare(actual, expected, sanitized_keys):
    """
        This function tries to sanitize actual and expected trees so that they can be processed by the differ.
        Both trees are processed with the following:
        - method is lowercased
        - headers keys are lowercased
        - headers keys are lowercased in matchingRules
        - query params are converted to a dict of lists
        - if one key is missing in ``expected``, remove it from ``actual``

        **The input trees are modified in place**.
    """
    def sanitize_empty_keys(actual, expected, keys):
        for key in keys:
            expected_value, _actual_value = expected.get(key, Empty), actual.get(key, Empty)
            if expected_value is Empty:
                actual.pop(key, None)  # No check at all if key is not in expected

    def apply_safe(function, x):
        try:
            return function(x)
        except:
            return x

    def format_header_value(header_value):
        return ','.join(value.strip(' ') for value in header_value.split(','))

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


def compare(actual, expected, path=None, matchers=None, ignore_extra_keys=True):
    """
        Build the diff tree of the two trees given as input.

        The resulting tree contains the same elements as ``actual`` and ``expected``
        when they match, and a Difference object when they don't.

        Args:
            path:
            matchers:
            ignore_extra_keys (bool): whether to ignore extra keys in the ``actual`` tree or not
    """
    path = path or '$.'
    matchers = matchers or {}

    if type(expected) == dict:
        if type(actual) != dict:
            return TypeNotMatched(actual, expected)
        return _compare_dicts(actual, expected, path, matchers, ignore_extra_keys)
    # Do not use collections.Sequence, it also matches strings which must be
    # treated as tree leaves.
    elif type(expected) in (list, tuple):
        if type(actual) not in (list, tuple):
            return TypeNotMatched(actual, expected)
        return _compare_lists(actual, expected, path, matchers, ignore_extra_keys)
    else:
        return _compare_values(actual, expected, path, matchers, ignore_extra_keys)


def _compare_dicts(actual, expected, path, matchers, ignore_extra_keys):
    diff_tree = {}
    for key, expected_value in expected.items():
        if key not in actual:
            diff_tree[key] = Difference(KeyNotFound, expected_value)
        else:
            actual_value = actual[key]
            diff_tree[key] = compare(
                actual_value,
                expected_value,
                path='%s.%s' % (path, key),
                matchers=matchers,
                ignore_extra_keys=ignore_extra_keys,
            )
    if not ignore_extra_keys:
        unexpected_keys = set(actual.keys()) - set(expected.keys())
        for key in unexpected_keys:
            diff_tree[key] = Difference(actual[key], UnexpectedKey)
    return diff_tree


def _compare_lists(actual, expected, path, matchers, ignore_extra_keys):
    diff_tree = []
    max_length = max(len(actual), len(expected))
    # TODO add min matcher
    for i in xrange(max_length):
        next_path = '%s[%s]' % (path, i)
        actual_value = actual[i] if i < len(actual) else IndexNotFound
        if i < len(expected):
            expected_value = expected[i]
        else:
            if expected and get_best_matcher(matchers, next_path):
                expected_value = expected[0]
            else:
                expected_value = UnexpectedIndex
        diff_tree.append(
            compare(
                actual_value,
                expected_value,
                matchers=matchers,
                path=next_path,
                ignore_extra_keys=ignore_extra_keys,
            )
        )
    return diff_tree


class PathMatcher(object):
    def __init__(self, regex, weight):
        self._regex = re.compile(regex)
        self._weight = weight

    def match(self, path):
        return bool(re.match(self._regex, path))

    def weight(self, path):
        return self._weight if self.match(path) else 0

    @classmethod
    def from_jsonpath(cls, jsonpath):
        # Use some regex to build a regex from a jsonpath… inception
        # Some rules applying to jsonpath:
        #   it must start with a dollar sign
        #   ] and ' characters are not allowed in keys between brackets
        #   [ and ] characters are not allowed in keys between dots
        #   [] and [*] match any list index
        assert jsonpath.startswith('$')
        jsonpath = '.%s' % jsonpath  # pre-process so that the $ character can be handled like any other

        match_dot_re = r"(?<=\.)(?P<dot>[^.\[\]]*)"
        match_bracket_re = r"(?<=\[)(?P<bracket>(?P<quote>')?[^'\]]*(?(quote)')\])"
        jsonpath_re = re.compile(r"%s|%s" % (match_dot_re, match_bracket_re))

        regex = r''
        weight = 1
        star_factor, exact_factor = 1, 2
        split = re.findall(jsonpath_re, jsonpath)
        for i, (dot_match, bracket_match, _quote) in enumerate(split):
            if bracket_match:
                # We kept the final bracket in the group to distinguish between
                # a dot match and a bracket match. Otherwise both could be
                # equal to the empty string. Now it's time to remove it.
                bracket_match = bracket_match[:-1]
                if bracket_match in ('*', ''):
                    regex += r"\[[0-9]+\]"
                    weight *= star_factor
                else:
                    if not bracket_match.startswith("'"):
                        try:
                            int(bracket_match)
                        except ValueError:
                            raise
                    regex += r"\[%s\]" % re.escape(bracket_match)
                    weight *= exact_factor
            else:
                if not dot_match:
                    regex += r"\[\'[^']*\'\]"
                    weight *= star_factor
                else:
                    if dot_match == '*':
                        if i == len(split) - 1:  # ending star
                            regex += r".*"
                        else:
                            regex += r"\[\'.*\'\]"
                        weight *= star_factor
                    else:
                        regex += r"\[\'%s\'\]" % re.escape(dot_match)
                        weight *= exact_factor
        return cls(regex, weight)


def test_regex():
    path = "$.toto.titi['tutu']"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']['titi']['tutu']")

    path = "$.toto.titi['tutu'].*"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']['titi']['tutu']['cucu']['kiki']")

    path = "$.toto.titi[*].*"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']['titi'][2]['cucu']['kiki']")
    assert not regex.match("['$']['toto']['titi']['tata']['cucu']['kiki']")

    path = "$.toto.titi.*.toto[0]"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']['titi']['cucu']['toto'][0]")
    assert not regex.match("['$']['toto']['titi']['cucu']['toto'][1]")

    test_weight()


def test_weight():
    test_cases = [
        ('$', 2),
        ('$.body', 4),
        ('$.body.item1', 8),
        ('$.body.item2', 0),
        ('$.header.item1', 0),
        ('$.body.item1.level', 16),
        ('$.body.item1.level[1]', 32),
        ('$.body.item1.level[1].id', 64),
        ('$.body.item1.level[1].name', 0),
        ('$.body.item1.level[2]', 0),
        ('$.body.item1.level[2].id', 0),
        ('$.body.item1.level[*].id', 32),
        ('$.body..level[].id', 16),
    ]
    test_path = "['$']['body']['item1']['level'][1]['id']"
    for path, weight in test_cases:
        assert PathMatcher.from_jsonpath(path).weight(test_path) == weight


def path_weight(regex, path):
    pass


def get_best_matcher(matchers, path):
    pass


class Matcher(object):
    def match(self, value):
        raise NotImplementedError


class EqualityMatcher(Matcher):
    def __init__(self, expected):
        self.expected = expected

    def match(self, value):
        if self.expected == value:
            return value
        return Difference(value, self.expected)


class RegexMatcher(Matcher):
    def __init__(self, regex):
        self.regex = re.compile(regex)

    def match(self, value):
        if not re.match(self.regex, value):
            return RegexNotMatched(value, self.regex)
        return value


def _compare_values(actual, expected, path, matchers, ignore_extra_keys):
    matcher = get_best_matcher(matchers, path) or EqualityMatcher(expected)
    return matcher.match(actual)


def check_rule(rule, actual, expected):
    """
        Check that ``actual`` respects ``rule`` for the expected value.
    """
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


def rebuild_trees_from_diff(diff, errors):
    """
        Rebuild the actual and expected trees from the diff tree.

        The expected tree is modified with values from actual when those values
        match the expected rules. These trees can then be exported to json and
        compared to display a nice diff to the end user.
    """
    if type(diff) == dict:
        actual, expected = {}, {}
        for key, value in diff.items():
            actual_next, expected_next = rebuild_trees_from_diff(value, errors)
            actual[key] = actual_next
            expected[key] = expected_next
    elif type(diff) in (list, tuple, set):
        actual, expected = [], []
        for el in diff:
            actual_next, expected_next = rebuild_trees_from_diff(el, errors)
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
    """
        Travel actual and expected request trees and search for differences.
    """
    keys = ('method', 'path', 'query', 'headers', 'body')
    sanitized_keys = ('headers', 'query', 'body')
    ignore_extra_keys = ('headers',)

    return _checker(actual, expected, keys, sanitized_keys, ignore_extra_keys)


def response_checker(actual, expected):
    """
        Travel actual and expected response trees and search for differences.
    """
    keys = ('status', 'headers', 'body')
    sanitized_keys = ('headers', 'status', 'body')
    ignore_extra_keys = ('headers', 'body')

    return _checker(actual, expected, keys, sanitized_keys, ignore_extra_keys)


def _checker(actual, expected, keys, sanitized_keys, ignore_extra_keys):
    """
        Travel actual and expected trees and search for differences.
    """
    prepare(actual, expected, sanitized_keys=sanitized_keys)
    matchers = expected.pop('matchingRules', {})
    diff_tree = {}
    for key in keys:
        diff_tree[key] = compare(
            actual.get(key, None),
            expected.get(key, None),
            path='$.%s' % key,
            matchers=matchers,
            ignore_extra_keys=key in ignore_extra_keys,
        )

    errors = []
    actual, expected = rebuild_trees_from_diff(diff_tree, errors)
    format_diff(actual, expected)
    return not errors


def format_diff(actual, expected, with_color=True):
    added_re = re.compile('^([+] [^\n]*)\n$')
    removed_re = re.compile('^([-] [^\n]*)\n$')
    def colorize(x):
        if not with_color:
            return x
        ret = re.sub(added_re, r'\033[1;32m\1\n\033[0;m', x)
        if ret == x:
            ret = re.sub(removed_re, r'\033[1;31m\1\n\033[0;m', x)
        return ret

    keepends = True
    lines = difflib.unified_diff(
        (json.dumps(actual, sort_keys=True, indent=4) + '\n').splitlines(keepends),
        (json.dumps(expected, sort_keys=True, indent=4) + '\n').splitlines(keepends),
        fromfile='actual',
        tofile='expected',
    )
    sys.stdout.writelines([colorize(line) for line in lines])


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
    #failed = {'request': 0, 'response': 0}
    #path = sys.argv[1] if len(sys.argv) > 1 else None
    #if path:
    #    request_or_response = 'request' if os.path.join('testcases', 'request') in path else 'response'
    #    checker = {'request': request_checker, 'response': response_checker}[request_or_response]
    #    check_file(path, checker)
    #    sys.exit(0)
    #for root, dirs, files in os.walk('/Users/Seb/temp/pact-specification/testcases'):
    #    for file_ in files:
    #        if file_.split('.')[-1] == 'json':
    #            path = os.path.join(root, file_)
    #            request_or_response = 'request' if os.path.join('testcases', 'request') in path else 'response'
    #            checker = {'request': request_checker, 'response': response_checker}[request_or_response]
    #            if not check_file(path, checker):
    #                failed[request_or_response] += 1
    #if any(failed.values()):
    #    for k, v in failed.items():
    #        print '%s %ss failed' % (v, k)
    #else:
    #    print 'Success'
    test_regex()
