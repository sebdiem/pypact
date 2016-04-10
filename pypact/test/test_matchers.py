import pytest

from ..matchers import PathMatcher, ValueMatcher

def json_path_testcases():
    return [
        {
            "json_path": "$.toto",
            "match": ["['$']['toto']"],
            "not_match": ["['$']['atoto']"]
        },
        {
            "json_path": "$[0]",
            "match": ["['$'][0]"],
            "not_match": ["['$']['0']", "['$'][1]"]
        },
        {
            "json_path": "$.toto.titi['tutu']",
            "match": ["['$']['toto']['titi']['tutu']"],
            "not_match": ["['$']['toto']['titi']['titu']", "['$']['tito']['titi']['tutu']"]
        },
        {
            "json_path": "$.toto['titi'].tutu",
            "match": ["['$']['toto']['titi']['tutu']"],
            "not_match": []
        },
        {
            "json_path": "$.toto.titi['tutu'].*",
            "match": ["['$']['toto']['titi']['tutu']['cucu']['kiki']"],
            "not_match": []
        },
        {
            "json_path": "$.toto.titi[*].*",
            "match": ["['$']['toto']['titi'][2]['cucu']['kiki']"],
            "not_match": ["['$']['toto']['titi']['tata']['cucu']['kiki']"]
        },
        {
            "json_path": "$.toto.titi.*.toto[0]",
            "match": ["['$']['toto']['titi']['cucu']['toto'][0]"],
            "not_match": ["['$']['toto']['titi']['cucu']['toto'][1]"]
        },
    ]


@pytest.fixture(params=json_path_testcases())
def json_path_testcase(request):
    return request.param


def test_json_path_to_regex(json_path_testcase):
    regex = PathMatcher.from_jsonpath(json_path_testcase['json_path'])
    for path in json_path_testcase['match']:
        assert regex.match(path)
    for path in json_path_testcase['not_match']:
        assert not regex.match(path)


def weight_testcases():
    return [
        {"json_path": '$.*', "weight": 2},
        {"json_path": '$.body.*', "weight": 4},
        {"json_path": '$.body.item1.*', "weight": 8},
        {"json_path": '$.body.item2.*', "weight": 0},
        {"json_path": '$.header.item1.*', "weight": 0},
        {"json_path": '$.body.item1.level.*', "weight": 16},
        {"json_path": '$.body.item1.level[1].*', "weight": 32},
        {"json_path": '$.body.item1.level[1].id.*', "weight": 64},
        {"json_path": '$.body.item1.level[1].name.*', "weight": 0},
        {"json_path": '$.body.item1.level[2].*', "weight": 0},
        {"json_path": '$.body.item1.level[2].id', "weight": 0},
        {"json_path": '$.body.item1.level[*].id', "weight": 32},
        {"json_path": '$.body..level[].id.*', "weight": 16},
    ]


@pytest.fixture(params=weight_testcases())
def weight_testcase(request):
    return request.param


def test_json_path_weight(weight_testcase):
    test_path = "['$']['body']['item1']['level'][1]['id']"
    path, weight = weight_testcase["json_path"], weight_testcase["weight"]
    assert PathMatcher.from_jsonpath(path).weight(test_path) == weight


def test_value_matchers_default_to_equality():
    assert ValueMatcher.from_dict({"toto": "nonsense"}).diff('actual', 'actual') is None
    assert ValueMatcher.from_dict({"toto": "nonsense"}).diff('actual', 'expected') is not None


def test_value_matchers_type_matcher():
    assert ValueMatcher.from_dict({"match": "type"}).diff('actual', 'expected') is None
    assert ValueMatcher.from_dict({"match": "type"}).diff(1, 2) is None
    assert ValueMatcher.from_dict({"match": "type"}).diff(1, 'oups') is not None


def test_value_matchers_regex_matcher():
    assert ValueMatcher.from_dict({"match": "regex", "regex": "[1-9]+"}).diff(1, None) is None
    assert ValueMatcher.from_dict({"match": "regex", "regex": "[1-9]+"}).diff(0, None) is not None
    assert ValueMatcher.from_dict({"match": "regex", "regex": "\\d+"}).diff('actual', None) is not None


def test_value_matchers_number_matcher():
    assert ValueMatcher.from_dict({"match": "type", "min": 1}).diff(['toto'], ['titi']) is None
    assert ValueMatcher.from_dict({"match": "type", "min": 1}).diff(['toto', 'tutu'], ['titi']) is None
    assert ValueMatcher.from_dict({"match": "type", "min": 1}).diff([], ['titi']) is not None
    assert ValueMatcher.from_dict({"match": "type", "max": 1}).diff([], ['titi']) is None
    assert ValueMatcher.from_dict({"match": "type", "max": 1}).diff(['toto'], ['titi']) is None
    assert ValueMatcher.from_dict({"match": "type", "max": 1}).diff(['toto', 'oups'], ['titi']) is not None
    assert ValueMatcher.from_dict({"match": "type", "min": 1, "max": 1}).diff(['toto'], ['titi']) is None
    assert ValueMatcher.from_dict({"match": "type", "min": 1, "max": 1}).diff([], ['titi']) is not None
    assert ValueMatcher.from_dict({"match": "type", "min": 1, "max": 1}).diff(['toto', 'oups'], ['titi']) is not None
