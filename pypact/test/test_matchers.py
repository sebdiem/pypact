from ..matchers import PathMatcher


def test_json_path_to_regex():
    path = "$.toto"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']")
    assert not regex.match("['$']['atoto']")

    path = "$[0]"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$'][0]")
    assert not regex.match("['$']['0']")
    assert not regex.match("['$'][1]")

    path = "$.toto.titi['tutu']"
    regex = PathMatcher.from_jsonpath(path)
    assert regex.match("['$']['toto']['titi']['tutu']")
    assert not regex.match("['$']['toto']['titi']['titu']")
    assert not regex.match("['$']['tito']['titi']['tutu']")

    path = "$.toto['titi'].tutu"
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
