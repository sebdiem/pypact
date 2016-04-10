from contextlib import contextmanager
import json
from urllib import urlencode

from django.db import DEFAULT_DB_ALIAS
from django.db import transaction

from . import base


class DjangoRestFrameworkClient(base.PactClientMock):
    def __init__(self, django_test_client, state_factory):
        self.client = django_test_client
        self.state_factory = state_factory

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
        """Hook the DRF http methods to return a Pact response object."""
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

    @contextmanager
    def set_up(self, init_states):
        with transaction.atomic(using=DEFAULT_DB_ALIAS):
            for name, params in init_states:
                getattr(self.state_factory, name)(**params)
            yield
