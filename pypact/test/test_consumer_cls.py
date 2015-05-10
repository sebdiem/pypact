import mock
import pytest

from ..consumer import Consumer


CONSUMER_NAME = "My Service Consumer"


@pytest.fixture
def consumer():
    return Consumer(name=CONSUMER_NAME)


def test_consumer_creation(consumer):
    assert consumer.name == CONSUMER_NAME


def test_consumer_pact(consumer):
    service_cls = mock.Mock()
    consumer.service_cls = service_cls
    mock_provider = mock.Mock()

    mock_service = consumer.has_pact_with(mock_provider, 1234)

    service_cls.assert_called_once_with(
        consumer=consumer, provider=mock_provider, port=1234)
    assert mock_service == service_cls.return_value
