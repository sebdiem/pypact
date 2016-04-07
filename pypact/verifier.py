import json
from urllib import urlencode

from django.db import DEFAULT_DB_ALIAS
from django.db import transaction


class BadPactFormat(Exception):
    pass


class step_and_rollback(object):
    def __init__(self, using=DEFAULT_DB_ALIAS):
        self.using = using
        self.transaction = None

    def __enter__(self):
        self.transaction = transaction.atomic(using=self.using)
        self.transaction.__enter__()

    def __exit__(self, *args, **kwargs):
        # Hack to rollback
        self.transaction.__exit__("Exit", None, None)



class DjangoRestFrameworkClient(object):
    def __init__(self, django_test_client):
        self.client = django_test_client

    @staticmethod
    def _format_header(header):
        return header.replace(' ', '_').replace('-', '_').upper()

    def _gen_extras_dict(self, headers, query):
        extras = {}
        if query:
            extras['QUERY_STRING'] = urlencode(query, doseq=True)
        headers = headers or {}
        extras.update((self._format_header(header), value) for header, value in headers.items())
        return extras

    def __getattribute__(self, attribute):
        if attribute in ('get', 'post', 'put', 'patch', 'delete'):
            def fun(self, path, data, headers, query):
                extras = self._gen_extras_dict(headers, query)
                response = getattr(self.client, attribute)(path=path, data=data, **extras)
                try:
                    content = json.loads(response.content)
                except:
                    content = response.content
                headers = dict(response.items())

                return {
                    'status': response.status_code,
                    'body': content,
                    'headers': headers,
                }
            return fun
        else:
            return super(DjangoRestFrameworkClient, self).__getattribute__(attribute)


def _get_pact(pact_uri):
    with open(pact_uri, 'r') as pact_file:
        pact = json.load(pact_file)
    return pact


class Provider(object):
    def __init__(self, pact_uri, client, state_module):
        self.pact = _get_pact(pact_uri)
        self.client = client
        self.state_module = state_module

    def set_up(self, init_states):
        for state in init_states:
            name = state['name'].replace(' ', '_')
            params = state['params']
            getattr(self.state_module, name)(**params)

    def honours_pact_with(self, consumer):
        assert self.pact['consumer']['name'] == consumer
        for interaction in self.pact['interactions']:
            with step_and_rollback():
                self.set_up(init_states=interaction.get('providerStates') or [])
                method = getattr(self.client, interaction['request']['method'].lower(), None)
                if not method:
                    raise Exception
                request = interaction['request']
                response = method(
                    self.client,
                    path=request['path'],
                    data=request.get('data', None),
                    headers=request.get('headers', None),
                    query=request.get('query', None),
                )
                diff = compare(response, interaction['response'])
                if diff:
                    raise AssertionError(diff)


def compare(actual, expected):
    # simple funnction, replace me
    if actual['status'] != expected['status']:
        return 'Error %s, %s' % (actual['status'], expected['status'])
    return ''
