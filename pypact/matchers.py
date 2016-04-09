# -*- coding: utf-8 -*-

import logging
import re


logger = logging.getLogger(__name__)


class BaseError(object):
    """Base class for errors when comparing two trees."""


class UnexpectedKey(BaseError):
    """The key was not found in the expected tree."""


class KeyNotFound(BaseError):
    """The expected key was not found in the actual tree."""


class UnexpectedIndex(BaseError):
    """The index was not found in the expected tree."""


class IndexNotFound(BaseError):
    """The expected index was not found in the actual tree."""


class Difference(BaseError):
    """Used to store a difference between an expected value and the actual one."""
    def __init__(self, actual, expected):
        self.actual = actual
        self.expected = expected

    def split(self):
        convert = lambda x: getattr(x, '__name__', x)
        return convert(self.actual), convert(self.expected)


class RegexNotMatched(Difference):
    """Used to store an actual value that does not match the expected regex."""


class TypeNotMatched(Difference):
    """Used to store an actual value that does not match the expected type."""
    def split(self):
        actual, expected = super(TypeNotMatched, self).split()
        return actual, '%s(%s)' % (self.__class__.__name__, expected)


class NumberNotMatched(BaseError):
    """Used to store an actual value that does not match the expected number of elements."""
    def __init__(self, actual, expected, minimum=None, maximum=None):
        self.actual = actual
        self.expected = expected
        self.minimum = minimum
        self.maximum = maximum

    def split(self):
        actual = "%s(min=%s, max=%s, %s)" % (self.__class__.__name__, self.minimum, self.maximum, self.actual)
        return actual, self.expected


class PathMatcher(object):
    """
        Stores a json_path as a regex with a weight.

        It enables to quickly determine if a given path inside a tree structure
        matches the json_path. The weight is a mean to compare two PathMatcher
        both matched by the same path and choose the more precise one.
    """
    def __init__(self, regex, weight):
        self._regex = re.compile(regex)
        self._weight = weight

    def match(self, path):
        return bool(re.match(self._regex, path))

    def weight(self, path):
        return self._weight if self.match(path) else 0

    @classmethod
    def from_jsonpath(cls, jsonpath):
        """
            Use some regex to build a regex from a jsonpath… inception

            Some rules applying to ``jsonpath``:
              it must start with a dollar sign
              ] and ' characters are not allowed in keys between brackets
              [ and ] characters are not allowed in keys between dots
              [] and [*] match any list index
        """
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
        regex += r"$"
        return cls(regex, weight)


class ValueMatcher(object):
    """
        Base class for PACT rules.

        It is used to compare the actual element with the expected one.
    """
    def diff(self, actual, expected):
        raise NotImplementedError

    @classmethod
    def from_dict(cls, d):
        if d.get('match'):
            match = d['match']
            if match == 'regex':
                return RegexMatcher(d['regex'])
            if match == 'type':
                if d.get('min') or d.get('max'):
                    return MinMaxMatcher(d.get('min'), d.get('max'))
                return TypeMatcher()
        elif d.get('min') or d.get('max'):
            return MinMaxMatcher(d.get('min'), d.get('max'))
        logger.debug('Unrecognised matcher %s, defaulting to equality matching', d)
        return EqualityMatcher()


class EqualityMatcher(ValueMatcher):
    def diff(self, actual, expected):
        if expected != actual:
            return Difference(actual, expected)


class RegexMatcher(ValueMatcher):
    def __init__(self, regex):
        self.regex = re.compile(regex)

    def diff(self, actual, expected=None):
        if not re.match(self.regex, actual):
            return RegexNotMatched(actual, self.regex.pattern)


class MinMaxMatcher(ValueMatcher):
    def __init__(self, minimum=None, maximum=None):
        if minimum and maximum:
            assert minimum <= maximum
        self.minimum = minimum
        self.maximum = maximum

    def diff(self, actual, expected):
        if self.minimum and len(actual) < self.minimum:
            return NumberNotMatched(actual, expected, minimum=self.minimum)
        if self.maximum and len(actual) > self.maximum:
            return NumberNotMatched(actual, expected, maximum=self.maximum)


class TypeMatcher(ValueMatcher):
    def diff(self, actual, expected):
        if type(expected) != type(actual):
            return TypeNotMatched(actual, expected)


def get_best_matcher(matchers, path):
    """
        Get the ValueMatcher that best matches path (in terms of weight).

        Args:
            matchers, list: a list of (PathMatcher, ValueMatcher)
            path, str: the path for which to get the ValueMatcher

        Return: ValueMatcher or None
    """
    if matchers:
        path_matcher, value_matcher = max(matchers, key=lambda x: x[0].weight(path))
        if path_matcher.weight(path):
            return value_matcher
