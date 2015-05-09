import pytest

import pypact


PROVIDER_NAME = "My Service Provider"


@pytest.mark.parametrize("args,kwargs", [
    ([PROVIDER_NAME], {}),
    ([], {'name': PROVIDER_NAME}),
])
def test_provider_creation(args, kwargs):
    provider = pypact.Provider(*args, **kwargs)

    assert provider.name == PROVIDER_NAME
