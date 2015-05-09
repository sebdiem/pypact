"""
PyPact exception classes
"""


class PyPactException(Exception):
    """
    Base PyPact exception.
    """
    pass


class PyPactServiceException(PyPactException):
    """
    Raised by MockService.
    """
    pass
