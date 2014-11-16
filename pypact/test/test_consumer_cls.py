import pytest

import pypact


CONSUMER_NAME = "My Service Consumer"


@pytest.mark.parametrize("args,kwargs", [
    ([CONSUMER_NAME], {}),
    ([], {'name': CONSUMER_NAME}),
])
def test_consumer_creation(args, kwargs):
    consumer = pypact.Consumer(*args, **kwargs)

    assert consumer.name == CONSUMER_NAME
