from .exceptions import PyPactException


class MockService(object):
    """
    Interface to interact with pact mock server.
    """

    def __init__(self, consumer, provider, port, interaction_builder=None):
        self.consumer = consumer
        self.provider = provider
        self.port = port
        self.interaction_builder = interaction_builder

        self.stopped = True
        self.interactions = []

    def given(self, state):
        if not self.stopped:
            raise PyPactException(
                "Cannot build interaction on started MockService")

        return self.interaction_builder.given(state, self.add_interaction)

    def upon_receiving(self, description):
        if not self.stopped:
            raise PyPactException(
                "Cannot build interaction on started MockService")

        return (
            self.interaction_builder
                .upon_receiving(description, self.add_interaction))

    def add_interaction(self, interaction):
        """
        Add a new interaction to the mock service.
        """
        if not self.stopped:
            raise PyPactException(
                "Cannot add interaction to already started MockService.")

        self.interactions.append(interaction)

    def start(self):
        """
        Start the mock service, loading the interactions into the pact server.
        """
        if not self.stopped:
            raise PyPactException("Cannot start already started MockService.")

        self.stopped = False

    def end(self):
        """
        End the mock service, verifing the interactions with the pact server.
        """
        if self.stopped:
            raise PyPactException("Cannot end already ended MockService.")

        self.stopped = True

    def __enter__(self):
        self.start()

    def __exit__(self, type, value, traceback):
        self.end()
