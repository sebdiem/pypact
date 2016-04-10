from contextlib import contextmanager
import json

from .. import validator


class BadPactFormat(Exception):
    pass


class PactClientMock(object):
    def get(self, path, data, headers, query):
        raise NotImplementedError

    def post(self, path, data, headers, query):
        raise NotImplementedError

    def put(self, path, data, headers, query):
        raise NotImplementedError

    def patch(self, path, data, headers, query):
        raise NotImplementedError

    def delete(self, path, data, headers, query):
        raise NotImplementedError

    @contextmanager
    def set_up(self, init_states):
        raise NotImplementedError


def _get_pact(pact_uri):
    with open(pact_uri, 'r') as pact_file:
        pact = json.load(pact_file)
    return pact


class Provider(object):
    def __init__(self, pact_uri, client):
        self.pact = _get_pact(pact_uri)
        self.client = client

    def get_and_assert_key(self, key):
        ret, path = self.pact, ''
        for k in key.split('.'):
            try:
                k = int(k)
            except ValueError:
                pass
            try:
                ret = ret[k]
                path += '%s%s' % ('.' if path else '', k)
            except KeyError:
                raise BadPactFormat('key %s not found' % path)
        return ret

    def honours_pact_with(self, consumer):
        assert self.get_and_assert_key('consumer.name') == consumer
        for i, interaction in enumerate(self.get_and_assert_key('interactions')):
            init_states = [(s['name'].replace(' ', '_'), s['params']) for s in interaction.get('providerStates', [])]
            with self.client.set_up(init_states=init_states):
                method = self.get_and_assert_key('interactions.%s.request.method' % i).lower()
                method = getattr(self.client, method, None)
                if not method:
                    raise BadPactFormat('method %s is not a valid method' % method)
                request = interaction['request']
                path = self.get_and_assert_key('interactions.%s.request.path' % i)
                response = method(
                    self.client,
                    path=path,
                    data=request.get('data', None),
                    headers=request.get('headers', None),
                    query=request.get('query', None),
                )
                expected_response = self.get_and_assert_key('interactions.%s.response' % i)
                diff = ''.join(validator.compare_responses(response, expected_response))
                if diff:
                    raise AssertionError(diff)
