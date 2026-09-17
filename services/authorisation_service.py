from typing import cast

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request

_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


class AuthorisationService:
    def __init__(self):
        credentials, _ = google.auth.default()
        self._credentials = self.__ensure_scoped_credentials(credentials)

    def get_credentials_token(self) -> str:
        try:
            self._credentials.refresh(Request())
        except Exception as error:
            raise RuntimeError(
                "Could not refresh Application Default Credentials. Ensure the "
                "Cloud Function has a runtime service account."
            ) from error

        token = self._credentials.token
        if not token:
            raise RuntimeError(
                "Application Default Credentials returned an empty access token"
            )
        return cast(str, token)

    @staticmethod
    def __ensure_scoped_credentials(credentials: Credentials) -> Credentials:
        if getattr(credentials, "requires_scopes", False):
            with_scopes = getattr(credentials, "with_scopes", None)
            if callable(with_scopes):
                return cast(Credentials, with_scopes([_CLOUD_PLATFORM_SCOPE]))

        return credentials
