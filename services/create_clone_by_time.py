import functions_framework
import requests
import google.auth
import google.auth.transport.requests


@functions_framework.http
def hello_http(request):
    credentials, project_id = google.auth.default()
    credentials.refresh(google.auth.transport.requests.Request())
    headers = {
        "Authorization": "Bearer {}".format(credentials.token),
        "Content-Type": "application/json"
    }

    response = requests.post(
        'URL',
        headers=headers,

        json={"cloneContext": {"kind": "sql#cloneContext", "destinationInstanceName": "blaise-dev-0aa908fa-clone",
                               "pointInTime": "2023-11-06T17:23:59.648821586Z"}})

    print(response.text)
    return response.text
