from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import Mock, patch

import pytest

from services.authorisation_service import AuthorisationService


@patch("services.authorisation_service.google.auth.default")
def test_get_credentials_token_uses_refreshed_google_credentials(
    mock_default: Mock,
) -> None:
    credentials = SimpleNamespace(token="token-from-adc")
    credentials.refresh = Mock()
    mock_default.return_value = (credentials, "project-id")

    service = AuthorisationService()

    token = service.get_credentials_token()

    assert token == "token-from-adc"
    credentials.refresh.assert_called_once()


@patch("services.authorisation_service.google.auth.default")
def test_authorisation_service_scopes_credentials_when_required(
    mock_default: Mock,
) -> None:
    scoped_credentials = cast(Any, SimpleNamespace(token="scoped-token"))
    scoped_credentials.refresh = Mock()

    credentials = cast(Any, SimpleNamespace(requires_scopes=True))
    credentials.with_scopes = Mock(return_value=scoped_credentials)
    mock_default.return_value = (credentials, "project-id")

    service = AuthorisationService()

    token = service.get_credentials_token()

    assert token == "scoped-token"
    credentials.with_scopes.assert_called_once_with(
        ["https://www.googleapis.com/auth/cloud-platform"]
    )


@patch("services.authorisation_service.google.auth.default")
def test_get_credentials_token_raises_when_adc_refresh_fails(
    mock_default: Mock,
) -> None:
    credentials = SimpleNamespace(token=None)
    credentials.refresh = Mock(side_effect=RuntimeError("adc failed"))
    mock_default.return_value = (credentials, "project-id")

    service = AuthorisationService()

    with pytest.raises(
        RuntimeError,
        match="Could not refresh Application Default Credentials",
    ):
        service.get_credentials_token()
