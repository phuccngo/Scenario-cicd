import requests
import pytest
from sqlalchemy.exc import OperationalError
from send_errors import (
    SendError, RetryableSendError, NonRetryableSendError,
    is_retryable_status, is_retryable_exception,
)

@pytest.mark.parametrize("code", [408, 425, 429, 500, 502, 503, 599])
def test_retryable_status(code):
    assert is_retryable_status(code)

@pytest.mark.parametrize("code", [200, 400, 401, 403, 404, 422])
def test_non_retryable_status(code):
    assert not is_retryable_status(code)

def test_none_status():
    assert not is_retryable_status(None)

def test_custom_send_errors():
    assert is_retryable_exception(SendError())
    assert is_retryable_exception(RetryableSendError())
    assert not is_retryable_exception(NonRetryableSendError())

def test_network_errors_are_retryable():
    assert is_retryable_exception(requests.Timeout())
    assert is_retryable_exception(requests.ConnectionError())

@pytest.mark.parametrize("code, expected", [(429, True), (503, True), (400, False), (403, False)])
def test_http_error_status(code, expected):
    response = requests.Response()
    response.status_code = code
    assert is_retryable_exception(requests.HTTPError(response=response)) is expected

def test_http_error_without_response():
    assert not is_retryable_exception(requests.HTTPError("missing response"))

def test_operational_error_is_retryable():
    exc = OperationalError("statement", {}, Exception("db unavailable"))
    assert is_retryable_exception(exc)

@pytest.mark.parametrize("exc", [
    ValueError("bad"), KeyError("missing"), TypeError("wrong"), AttributeError("missing"),
])
def test_data_errors_are_not_retryable(exc):
    assert not is_retryable_exception(exc)

def test_unknown_exception_defaults_to_retryable():
    assert is_retryable_exception(RuntimeError("unknown"))
