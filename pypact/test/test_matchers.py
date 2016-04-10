import pytest

from ..matchers import PathMatcher

def json_path_testcases():
    # return a list of (json_path, paths_expected_to_match, paths_expected_not_to_match)
    return [
        ("$.toto", ["['$']['toto']"], ["['$']['atoto']"]),
        ("$[0]", ["['$'][0]"], ["['$']['0']", "['$'][1]"]),
        (
            "$.toto.titi['tutu']",
            ["['$']['toto']['titi']['tutu']"],
            ["['$']['toto']['titi']['titu']", "['$']['tito']['titi']['tutu']"]
        ),
        ("$.toto['titi'].tutu", ["['$']['toto']['titi']['tutu']"], []),
        ("$.toto.titi['tutu'].*", ["['$']['toto']['titi']['tutu']['cucu']['kiki']"], []),
        (
            "$.toto.titi[*].*",
            ["['$']['toto']['titi'][2]['cucu']['kiki']"],
            ["['$']['toto']['titi']['tata']['cucu']['kiki']"]
        ),
        (
            "$.toto.titi.*.toto[0]",
            ["['$']['toto']['titi']['cucu']['toto'][0]"],
            ["['$']['toto']['titi']['cucu']['toto'][1]"]
        ),
    ]


@pytest.fixture(params=json_path_testcases())
def test_json_path_to_regex(json_path_testcase):
    json_path, match, not_match = json_path_testcase
    regex = PathMatcher.from_jsonpath(json_path)
    for path in match:
        assert regex.match(path)
    for path in not_match:
        assert not regex.match(path)


def test_json_path_weight():
    test_cases = [
        ('$.*', 2),
        ('$.body.*', 4),
        ('$.body.item1.*', 8),
        ('$.body.item2.*', 0),
        ('$.header.item1.*', 0),
        ('$.body.item1.level.*', 16),
        ('$.body.item1.level[1].*', 32),
        ('$.body.item1.level[1].id.*', 64),
        ('$.body.item1.level[1].name.*', 0),
        ('$.body.item1.level[2].*', 0),
        ('$.body.item1.level[2].id', 0),
        ('$.body.item1.level[*].id', 32),
        ('$.body..level[].id.*', 16),
    ]
    test_path = "['$']['body']['item1']['level'][1]['id']"
    for path, weight in test_cases:
        assert PathMatcher.from_jsonpath(path).weight(test_path) == weight


def test_value_matchers():
    pass
