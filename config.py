import json
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import google.auth
import requests
from google.auth.transport.requests import Request
from google.cloud import secretmanager

_BLAISE_INSTANCE_NAME_PATTERN = re.compile(
    r"^blaise-[a-z0-9-]+-[a-z0-9-]{8,}$", re.IGNORECASE
)
_MIN_EXPECTED_INSTANCE_NAME_PARTS = 3


def parse_uk_local_timestamp(value: str) -> datetime:
    cleaned = value.strip()
    normalized = cleaned.replace("T", " ")

    local_naive = datetime.fromisoformat(normalized)
    if local_naive.tzinfo is not None:
        return local_naive

    return local_naive.replace(tzinfo=ZoneInfo("Europe/London"))


def discover_project_id() -> str:
    try:
        _, project_id = google.auth.default()
        if project_id:
            return str(project_id)
    except Exception:
        # Fall back to the gcloud CLI if application default credentials fail.
        pass

    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            check=True,
            capture_output=True,
            text=True,
        )
        project_id = result.stdout.strip()
        if project_id and project_id != "(unset)":
            return project_id
    except Exception:
        # The error is reported by the explicit exit message below.
        pass

    sys.exit(
        "Error: Could not determine the active GCP project. "
        "Authenticate with gcloud and run 'gcloud config set project <PROJECT_ID>'."
    )


def _discover_access_token() -> str:
    try:
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
        token = str(credentials.token)
        if token:
            return token
    except Exception:
        # Fall back to the gcloud CLI if application default credentials fail.
        pass

    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            check=True,
            capture_output=True,
            text=True,
        )
        token = result.stdout.strip()
        if token:
            return token
    except Exception:
        # The error is reported by the explicit exit message below.
        pass

    sys.exit(
        "Error: Could not acquire GCP access token. "
        "Authenticate with 'gcloud auth application-default login'."
    )


def discover_destination_instance_name(project_id: str) -> str:
    instances: list[tuple[str, str]] = []

    try:
        token = _discover_access_token()
        response = requests.get(
            url=(
                "https://sqladmin.googleapis.com/sql/v1beta4/projects/"
                f"{project_id}/instances"
            ),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()

        response_instances = response.json().get("items", [])
        instances = [
            (str(instance["name"]), str(instance["connectionName"]))
            for instance in response_instances
            if "name" in instance and "connectionName" in instance
        ]
    except Exception:
        instances = []

    if not instances:
        try:
            result = subprocess.run(
                [
                    "gcloud",
                    "sql",
                    "instances",
                    "list",
                    "--project",
                    project_id,
                    "--format=json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            parsed_instances = json.loads(result.stdout)
            if isinstance(parsed_instances, list):
                instances = [
                    (str(instance["name"]), str(instance["connectionName"]))
                    for instance in parsed_instances
                    if isinstance(instance, dict)
                    and "name" in instance
                    and "connectionName" in instance
                ]
            else:
                instances = []
        except Exception:
            try:
                legacy_result = subprocess.run(
                    [
                        "gcloud",
                        "sql",
                        "instances",
                        "list",
                        "--project",
                        project_id,
                        "--format=value(connectionName)",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                instances = [
                    (line.rsplit(":", maxsplit=1)[-1], line)
                    for line in legacy_result.stdout.splitlines()
                    if line.strip()
                ]
            except Exception:
                instances = []

    if not instances:
        sys.exit(
            "Error: Could not discover a Cloud SQL instance automatically. "
            "Ensure gcloud auth works and a project is configured."
        )

    eligible_instances = [
        instance
        for instance in instances
        if _BLAISE_INSTANCE_NAME_PATTERN.match(instance[0])
    ]

    if len(eligible_instances) == 1:
        return eligible_instances[0][1]

    if not eligible_instances:
        discovered_instance_names = ", ".join(
            sorted(instance_name for instance_name, _ in instances)
        )
        sys.exit(
            "Error: No Cloud SQL instance matched expected naming convention "
            "'blaise-<env>-<random-guid>'. Discovered instances: "
            f"{discovered_instance_names}"
        )

    matched_instance_names = ", ".join(
        sorted(instance_name for instance_name, _ in eligible_instances)
    )
    sys.exit(
        "Error: Multiple Cloud SQL instances matched expected naming convention "
        "'blaise-<env>-<random-guid>'. Refusing to choose automatically. "
        "Matched instances: "
        f"{matched_instance_names}"
    )


def discover_database_name(project_id: str, instance_connection_name: str) -> str:
    instance_name = instance_connection_name.rsplit(":", maxsplit=1)[-1]
    database_names: list[str] = []

    try:
        token = _discover_access_token()
        response = requests.get(
            url=(
                "https://sqladmin.googleapis.com/sql/v1beta4/projects/"
                f"{project_id}/instances/{instance_name}/databases"
            ),
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        response.raise_for_status()

        items = response.json().get("items", [])
        database_names = [str(item["name"]) for item in items if "name" in item]
    except Exception:
        database_names = []

    if not database_names:
        try:
            result = subprocess.run(
                [
                    "gcloud",
                    "sql",
                    "databases",
                    "list",
                    "--project",
                    project_id,
                    "--instance",
                    instance_name,
                    "--format=value(name)",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            database_names = [
                line.strip() for line in result.stdout.splitlines() if line.strip()
            ]
        except Exception:
            database_names = []

    if not database_names:
        sys.exit(
            "Error: Could not discover the destination database name automatically."
        )

    system_database_names = {
        "cloudsqladmin",
        "information_schema",
        "mysql",
        "performance_schema",
        "sys",
    }
    user_databases = [
        name for name in database_names if name.lower() not in system_database_names
    ]

    if len(user_databases) == 1:
        return user_databases[0]

    if len(user_databases) > 1:
        preferred_names = [name for name in user_databases if name.lower() == "blaise"]
        if len(preferred_names) == 1:
            return preferred_names[0]

        discovered_user_databases = ", ".join(sorted(user_databases))
        sys.exit(
            "Error: Multiple non-system databases found and no unambiguous "
            "database could be selected automatically. "
            f"Discovered user databases: {discovered_user_databases}"
        )

    discovered_databases = ", ".join(sorted(database_names))
    sys.exit(
        "Error: No non-system database found for destination instance. "
        "Refusing to use a system database automatically. "
        f"Discovered databases: {discovered_databases}"
    )


def discover_database_username() -> str:
    return "blaise"


def discover_database_password(project_id: str) -> str:
    secret_name = "cloudsql_pw"

    try:
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_path = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        secret_version = secret_client.access_secret_version(name=secret_path)
        password_value = secret_version.payload.data.decode("UTF-8")
        if password_value:
            return password_value
    except Exception:
        # Fall back to the gcloud CLI if Secret Manager is unavailable.
        pass

    try:
        result = subprocess.run(
            [
                "gcloud",
                "secrets",
                "versions",
                "access",
                "latest",
                f"--secret={secret_name}",
                f"--project={project_id}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        password_value = result.stdout.strip()
        if password_value:
            return password_value
    except Exception:
        # The error is reported by the explicit exit message below.
        pass

    sys.exit(
        "Error: Could not discover destination database password automatically. "
        "Grant Secret Manager access for secret "
        f"'{secret_name}'."
    )


def discover_restore_bucket_name(instance_connection_name: str) -> str:
    instance_name = instance_connection_name.rsplit(":", maxsplit=1)[-1]
    parts = instance_name.split("-")
    if len(parts) < _MIN_EXPECTED_INSTANCE_NAME_PARTS or parts[0].lower() != "blaise":
        sys.exit(
            "Error: Could not infer environment from Cloud SQL instance name. "
            "Expected format like 'blaise-<env>-<id>'."
        )

    environment_name = parts[1].lower()
    return f"ons-blaise-v2-{environment_name}-backups"


class Settings:
    DEST_PROJECT_ID = discover_project_id()
    DEST_INSTANCE_NAME = discover_destination_instance_name(DEST_PROJECT_ID)
    RESTORE_SOURCE_INSTANCE_NAME = DEST_INSTANCE_NAME
    DEST_DB_NAME = discover_database_name(DEST_PROJECT_ID, DEST_INSTANCE_NAME)
    RESTORE_GCS_BUCKET = discover_restore_bucket_name(DEST_INSTANCE_NAME)
    RESTORE_GCS_PREFIX = "questionnaire-pitr"

    CLONE_NAME_PREFIX = "pitr"
    CLONE_OPERATION_POLL_SECONDS = 5
    CLONE_OPERATION_TIMEOUT_SECONDS = 1800
    CLONE_HTTP_CONNECT_TIMEOUT_SECONDS = 5.0
    CLONE_HTTP_READ_TIMEOUT_SECONDS = 30.0
