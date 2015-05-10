import json
import pytest
import requests
import requests_mock

from ..client import MockServerClient, CLIENT_HEADERS


TEST_BASE_URI = 'mock://127.0.0.1:1234'


@pytest.fixture
def client():
    return MockServerClient(TEST_BASE_URI)


@pytest.fixture
def mock_request(client):
    adapter = requests_mock.Adapter()
    client.mount('mock', adapter)
    return adapter


def test_client_creation(client):
    assert client.base_uri == TEST_BASE_URI

    for header in CLIENT_HEADERS.items():
        assert header in client.headers.items()


def test_client_get_verification(client, mock_request):
    mock_request.register_uri(
        'GET',
        '{}/interactions/verification'.format(TEST_BASE_URI),
        text='')

    verification = client.get_verification()

    assert verification == ''
    assert mock_request.call_count == 1


def test_client_put_interactions(client, mock_request):
    mock_request.register_uri(
        'PUT',
        '{}/interactions'.format(TEST_BASE_URI))

    client.put_interactions([{}])

    assert mock_request.call_count == 1
    assert mock_request.request_history[0].json() == [{}]


def test_client_delete_interactions(client, mock_request):
    mock_request.register_uri(
        'DELETE',
        '{}/interactions'.format(TEST_BASE_URI))

    client.delete_interactions()

    assert mock_request.call_count == 1


def test_client_post_interaction(client, mock_request):
    mock_request.register_uri('POST', '{}/interactions'.format(TEST_BASE_URI))

    client.post_interaction({})

    assert mock_request.call_count == 1
    assert mock_request.request_history[0].json() == {}


def test_client_post_pact(client, mock_request):
    mock_request.register_uri('POST', '{}/pact'.format(TEST_BASE_URI))

    client.post_pact({})

    assert mock_request.call_count == 1
    assert mock_request.request_history[0].json() == {}


REAL_CLIENT_URI = 'http://localhost:1234'


@pytest.fixture
def real_client(request):
    client = MockServerClient(REAL_CLIENT_URI)

    def fin():
        try:
            client.delete_interactions()
        except requests.ConnectionError:
            pass
    request.addfinalizer(fin)

    return client


@pytest.mark.integration
@pytest.mark.xfail(reason="Have to run the ruby pact-mock-service manually.")
def test_client_integration(real_client):

    real_client.post_interaction({
        'providerState': 'an alligator exists',
        'description': 'a request for an alligator',
        'request': {
            'method': 'get',
            'path': '/alligators',
            'query': '',
            'headers': {}
        },
        'response': {
            'status': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': [{'name': 'Betty'}]
        }
    })

    real_client.post_interaction({
        'providerState': 'an alligator exists',
        'description': 'post a new alligator',
        'request': {
            'method': 'post',
            'path': '/alligators',
            'query': '',
            'headers': {},
            'body': {'name': 'Terrance'}
        },
        'response': {
            'status': 200,
            'headers': {'Content-Type': 'application/json'}
        }
    })

    requests.get('{}/alligators'.format(REAL_CLIENT_URI))
    requests.post(
        '{}/alligators'.format(REAL_CLIENT_URI),
        headers={'Content-Type': 'application/json'},
        data=json.dumps({'name': 'Terrance'}))

    verification = real_client.get_verification()

    assert verification == 'Interactions matched'

    real_client.delete_interactions()
