# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import difflib
import json
import re
import urlparse

from . import matchers as matchers_module


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
            if key not in expected:
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
    path = path or "['$']"
    matchers = matchers or []

    if type(expected) == dict:
        if type(actual) != dict:
            return matchers_module.TypeNotMatched(actual, expected)
        return _compare_dicts(actual, expected, path, matchers, ignore_extra_keys)
    # Do not use collections.Sequence, it also matches strings which must be
    # treated as tree leaves.
    elif type(expected) in (list, tuple):
        if type(actual) not in (list, tuple):
            return matchers_module.TypeNotMatched(actual, expected)
        return _compare_lists(actual, expected, path, matchers, ignore_extra_keys)
    else:
        return _compare_values(actual, expected, path, matchers)


def _compare_dicts(actual, expected, path, matchers, ignore_extra_keys):
    diff_tree = {}
    for key, expected_value in expected.items():
        if key not in actual:
            diff_tree[key] = matchers_module.Difference(matchers_module.KeyNotFound, expected_value)
        else:
            actual_value = actual[key]
            diff_tree[key] = compare(
                actual_value,
                expected_value,
                path=_append_key_to_path(path, key),
                matchers=matchers,
                ignore_extra_keys=ignore_extra_keys,
            )
    if not ignore_extra_keys:
        unexpected_keys = set(actual.keys()) - set(expected.keys())
        for key in unexpected_keys:
            diff_tree[key] = matchers_module.Difference(actual[key], matchers_module.UnexpectedKey)
    return diff_tree


def _compare_lists(actual, expected, path, matchers, ignore_extra_keys):
    diff_tree = []
    max_length = max(len(actual), len(expected))
    value_matcher = matchers_module.get_best_matcher(matchers, path)
    if value_matcher:
        diff = value_matcher.diff(actual, expected)
        if diff:
            return diff

    for i in xrange(max_length):
        next_path = _append_index_to_path(path, i)
        actual_value = actual[i] if i < len(actual) else matchers_module.IndexNotFound
        if i < len(expected):
            expected_value = expected[i]
        else:
            if expected and matchers_module.get_best_matcher(matchers, next_path):
                expected_value = expected[0]
            else:
                expected_value = matchers_module.UnexpectedIndex
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


def _compare_values(actual, expected, path, matchers):
    matcher = matchers_module.get_best_matcher(matchers, path) or matchers_module.EqualityMatcher()
    return matcher.diff(actual, expected) or actual


def _append_key_to_path(path, key):
    # use bracket notation because this is what PathParser can handle
    if path is None:
        path = "['$']"
    return "%s['%s']" % (path, key)


def _append_index_to_path(path, index):
    if path is None:
        path = "['$']"
    return "%s[%s]" % (path, index)


def trees_from_diff(diff, errors):
    """
        Rebuild the actual and expected trees from the diff tree.

        The expected tree is modified with values from actual when those values
        match the expected rules. These trees can then be exported to json and
        compared to display a nice diff to the end user.
    """
    if type(diff) == dict:
        actual, expected = {}, {}
        for key, value in diff.items():
            actual_next, expected_next = trees_from_diff(value, errors)
            actual[key] = actual_next
            expected[key] = expected_next
    elif type(diff) in (list, tuple, set):
        actual, expected = [], []
        for el in diff:
            actual_next, expected_next = trees_from_diff(el, errors)
            actual.append(actual_next)
            expected.append(expected_next)
    else:
        if isinstance(diff, matchers_module.BaseError):
            errors.append(diff)
            actual, expected = diff.split()
        else:
            actual, expected = diff, diff
    return actual, expected


def compare_requests(actual, expected):
    """
        Travel actual and expected request trees and search for differences.
    """
    keys = ('method', 'path', 'query', 'headers', 'body')
    sanitized_keys = ('headers', 'query', 'body')
    ignore_extra_keys = ('headers',)

    return _compare_pacts(actual, expected, keys, sanitized_keys, ignore_extra_keys)


def compare_responses(actual, expected):
    """
        Travel actual and expected response trees and search for differences.
    """
    keys = ('status', 'headers', 'body')
    sanitized_keys = ('headers', 'status', 'body')
    ignore_extra_keys = ('headers', 'body')

    return _compare_pacts(actual, expected, keys, sanitized_keys, ignore_extra_keys)


def _compare_pacts(actual, expected, keys, sanitized_keys, ignore_extra_keys):
    """
        Travel actual and expected trees and search for differences.

        Return: an array of str representing the diff between actual and expected.
            If actual and expected match, the array is empty.
    """
    prepare(actual, expected, sanitized_keys=sanitized_keys)
    matchers = [
        (matchers_module.PathMatcher.from_jsonpath(path), matchers_module.ValueMatcher.from_dict(rule))
        for path, rule in expected.pop('matchingRules', {}).items()
    ]
    diff_tree = {}
    for key in keys:
        diff_tree[key] = compare(
            actual.get(key, None),
            expected.get(key, None),
            path=_append_key_to_path(path=None, key=key),
            matchers=matchers,
            ignore_extra_keys=key in ignore_extra_keys,
        )

    errors = []
    actual, expected = trees_from_diff(diff_tree, errors)
    diff = format_diff(actual, expected)
    return diff


def format_diff(actual, expected, with_color=True):
    added_re = re.compile('^([+][^+][^\n]*\n)$')
    removed_re = re.compile('^([-][^-][^\n]*\n)$')
    def colorize(x):
        if not with_color:
            return x
        ret = re.sub(added_re, r'\033[1;32m\1\033[0;m', x)
        if ret == x:
            ret = re.sub(removed_re, r'\033[1;31m\1\033[0;m', x)
        return ret

    keepends = True
    lines = difflib.unified_diff(
        (json.dumps(actual, sort_keys=True, indent=4) + '\n').splitlines(keepends),
        (json.dumps(expected, sort_keys=True, indent=4) + '\n').splitlines(keepends),
        fromfile='actual',
        tofile='expected',
    )
    return (colorize(line) for line in lines)
