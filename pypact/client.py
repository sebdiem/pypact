import json

import requests


CLIENT_HEADERS = {
    'X-Pact-Mock-Service': 'true',
    'Content-Type': 'application/json'
}


class MockServerClient(requests.Session):

    def __init__(self, base_uri, *args, **kwargs):
        super(MockServerClient, self).__init__(*args, **kwargs)

        self.base_uri = base_uri
        self.headers.update(CLIENT_HEADERS)

    def get_verification(self):
        return self.get(
            '{}/interactions/verification'.format(self.base_uri)
            ).text

    def put_interactions(self, interactions):
        self.put(
            '{}/interactions'.format(self.base_uri),
            data=json.dumps(interactions)
        )

    def delete_interactions(self):
        self.delete('{}/interactions'.format(self.base_uri))

    def post_interaction(self, interaction):
        self.post(
            '{}/interactions'.format(self.base_uri),
            data=json.dumps(interaction)
        )

    def post_pact(self, pact_details):
        self.post(
            '{}/pact'.format(self.base_uri),
            data=json.dumps(pact_details)
        )
