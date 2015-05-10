"""Provides API for managing service consumers"""
from .service import MockService


class Consumer(object):

    def __init__(self, name, service_cls=MockService):
        self.name = name
        self.service_cls = MockService

    def has_pact_with(self, provider, port):
        return self.service_cls(
            consumer=self,
            provider=provider,
            port=port)
