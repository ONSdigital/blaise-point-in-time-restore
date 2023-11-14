from google.auth.transport import requests
import requests

from models.database_clone_model import DatabaseCloneModel
from services.authorisation_service import AuthorisationService


class DatabaseCloneService:
    def __init__(self, authorisation_service: AuthorisationService, clone_api_url: str, delete_clone_api_url):
        self._authorisation_service = authorisation_service
        self._clone_api_url = clone_api_url
        self._delete_clone_api_url = delete_clone_api_url

    def create_clone(self, database_clone_model: DatabaseCloneModel):
        response = requests.post(
            url=self._clone_api_url,
            headers=self.__create_authorisation_headers(),
            json=self.__create_clone_request_body(database_clone_model))

        print(response.text)

        return response

    def delete_clone(self):
        response = requests.delete(url=self._delete_clone_api_url)
        print(response.text)


    def __create_authorisation_headers(self):
        token = self._authorisation_service.get_credentials_token()

        return {
            "Authorization": "Bearer {}".format(token),
            "Content-Type": "application/json"
        }

    @staticmethod
    def __create_clone_request_body(database_clone_model: DatabaseCloneModel):
        return {"cloneContext": {"kind": database_clone_model.source_instance_name,
                                 "destinationInstanceName": database_clone_model.destination_instance_name,
                                 "pointInTime": database_clone_model.point_in_time}}

