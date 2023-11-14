from Tools.scripts import google
import google.auth
from google.auth.transport import requests


class AuthorisationService:

    def __init__(self):
        self._credentials, self._project_id = google.auth.default()

    def get_credentials_token(self):
        self._credentials.refresh(google.auth.transport.requests.Request())

        return self._credentials.token
