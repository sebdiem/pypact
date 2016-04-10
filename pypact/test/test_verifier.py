from contextlib import contextmanager
import json
import tempfile

import pytest

from ..verifiers import base


@pytest.fixture()
def mock_client_class():
    class TestClientMock(base.PactClientMock):
        def __init__(self, fail=False):
            self.calls = []
            self.state = []
            self.fail = fail

        def get(self, *args, **kwargs):
            self.calls.append(('get', kwargs, self.state))
            name = 'Marie' if self.fail else 'Mary'
            return {
                "status": 200,
                "headers": {},
                "body": {'cows': [name]}
            }

        @contextmanager
        def set_up(self, init_states):
            self.state = init_states
            yield
            self.state = []  # clean after test
    return TestClientMock


PACT = json.dumps({
    "provider" : {
        "name" : "myAwesomeService"
    },
    "consumer" : {
        "name" : "anotherService"
    },
    "interactions" : [
        {
            "providerStates": [
                {
                    "name": "given one cow named",
                    "params": {
                        "name": "Mary"
                    }
                },
            ],
            "request": {
                "method" : "GET",
                "path": "zoo/cows",
                "data": {},
                "query": {},
                "headers": {},
            },
            "response": {
                "body": {
                    "cows": ["Mary"],
                }
            }
        }
    ]
})

def test_honours_pact_with(mock_client_class):
    with tempfile.NamedTemporaryFile() as f:
        f.write(PACT)
        f.seek(0)
        client = mock_client_class()
        provider = base.Provider(f.name, client)
        provider.honours_pact_with('anotherService')

        assert client.state == []
        assert client.calls == [
            (
                'get',
                {'data': {}, 'headers': {}, 'query': {}, 'path': 'zoo/cows'},
                [('given_one_cow_named', {'name': 'Mary'})]
            )
        ]

        with pytest.raises(AssertionError):
            provider = base.Provider(f.name, mock_client_class(fail=True))
            provider.honours_pact_with('anotherService')
