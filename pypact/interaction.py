class Interaction(object):
    """
    Builder for interaction dictionaries
    """

    def __init__(self, add_method):
        self.add_method = add_method

        self.provider_state = None
        self.description = None
        self.request = None
        self.response = None

    def given(self, provider_state):
        self.provider_state = provider_state
        return self

    def upon_receiving(self, description):
        self.description = description
        return self

    def with_request(self, method, path, query=None, headers=None, body=None):
        self.request = {
            'method': method.lower(),
            'path': path
        }

        if query is not None:
            self.request['query'] = query

        if headers is not None:
            self.request['headers'] = headers

        if body is not None:
            self.request['body'] = body

        return self

    def will_respond_with(self, status, headers=None, body=None):
        self.response = {
            'status': status
        }

        if headers is not None:
            self.response['headers'] = headers

        if body is not None:
            self.response['body'] = body

        self.add_interaction()

    def add_interaction(self):
        self.add_method({
            'provider_state': self.provider_state,
            'description': self.description,
            'request': self.request,
            'response': self.response
        })
