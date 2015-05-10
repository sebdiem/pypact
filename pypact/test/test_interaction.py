import mock
import pytest

from ..interaction import Interaction


TEST_STATE = "a state"
TEST_DESCRIPTION = "a request"
TEST_REQUEST = {
    'method': 'post',
    'path': '/path',
    'query': 'foo=bar',
    'headers': {'Custom-Header': 'value'},
    'body': {'key': 'value'}}
TEST_RESPONSE = {
    'status': 200,
    'headers': {'Custom-Header': 'value'},
    'body': {'key': 'value'}}


@pytest.fixture
def mock_add_method():
    return mock.Mock()


@pytest.fixture
def interaction(mock_add_method):
    return Interaction(mock_add_method)


def test_interaction_creation(interaction, mock_add_method):
    assert interaction.add_method == mock_add_method
    assert interaction.provider_state is None
    assert interaction.description is None
    assert interaction.request is None
    assert interaction.response is None


def test_interaction_given(interaction):
    chain = interaction.given(TEST_STATE)

    assert chain == interaction
    assert interaction.provider_state == TEST_STATE


def test_interaction_upon_receiving(interaction):
    chain = interaction.upon_receiving(TEST_DESCRIPTION)

    assert chain == interaction
    assert interaction.description == TEST_DESCRIPTION


def test_interaction_with_request(interaction):
    chain = interaction.with_request(**TEST_REQUEST)

    assert chain == interaction
    assert interaction.request == TEST_REQUEST


def test_interaction_with_response(interaction, mock_add_method):
    interaction.will_respond_with(**TEST_RESPONSE)

    assert interaction.response == TEST_RESPONSE

    assert mock_add_method.call_count == 1


def test_interaction_given_build(interaction, mock_add_method):
    (interaction
        .given("a state")
        .upon_receiving('a request')
        .with_request(
            method="post",
            path='/path',
            query='foo=bar',
            headers={'Custom-Header': 'value'},
            body={'key': 'value'})
        .will_respond_with(
            status=200,
            headers={'Custom-Header': 'value'},
            body={'key': 'value'}))

    assert mock_add_method.call_count == 1
