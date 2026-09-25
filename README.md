# Cloud SQL Table Point-in-Time Restore

This repository contains the source for a deployable HTTP Google Cloud Function. The function restores table data to a specific point in time by creating a temporary Cloud SQL clone, exporting the required tables to Cloud Storage, and importing them into the live database.

The Cloud Function is intended to be packaged and deployed by Terraform maintained in a separate infrastructure repository. This repository does not create infrastructure or deploy itself.

## Function Contract

- Runtime: Python 3.13
- Entry point: `restore_table_from_point_in_time`
- Trigger: HTTP
- Request content type: `application/json`
- Maximum execution time: 3600 seconds
- Recommended memory: at least 512 MiB

The function expects this request body:

```json
{
  "table_name": "LMS2601_KX2",
  "timestamp": "2026-07-08 14:30:00",
  "database_name": "blaise"
}
```

`timestamp` is parsed as UK local time (`Europe/London`) when no timezone offset is supplied. An ISO 8601 timestamp with an explicit offset is also accepted.

Google permits PITR timestamps up to 7 days old for non-production environments using the MySQL Enterprise edition. Production uses MySQL Enterprise Plus, which permits PITR timestamps up to 35 days old.

`table_name` identifies the table to restore. `database_name` identifies the database containing that table. Both values are case-sensitive and must use the exact casing of the table and database on the active Cloud SQL instance.

Successful requests return HTTP `200`. Validation failures return HTTP `400`, and restore failures return HTTP `500` with a request ID that can be matched to Cloud Logging entries.

## What Gets Restored

For the `blaise` database, `table_name` is treated as the base questionnaire table name and the following two tables are restored:

- `<TABLE_NAME>_Dml`
- `<TABLE_NAME>_Form`

For any other database, the exact table supplied in `table_name` is restored. The destination tables are restored from SQL export files generated from the clone.

## Deployment

The Terraform deployment must package the repository root so that `main.py` is at the root of the Cloud Function source archive.

The infrastructure must provide:

- A second-generation HTTP Cloud Function using the Python 3.13 runtime.
- A dedicated runtime service account.
- A VPC connector with access to the Cloud SQL instance.
- A timeout that accommodates the restore operation; 3600 seconds is recommended.
- Authentication on the HTTP endpoint. Do not allow unauthenticated invocation.
- Cloud SQL Admin permission for the runtime service account.
- Permission for the runtime service account to get and set the backup bucket IAM policy. `roles/storage.admin` may be used, or a custom role containing `storage.buckets.getIamPolicy` and `storage.buckets.setIamPolicy`.
- Cloud Run Invoker permission for operators who invoke the second-generation function.

The function uses Application Default Credentials from its runtime service account. Terraform must attach that service account to the function and provide the resource identifiers below as runtime environment variables. Do not pass access tokens, service-account keys, or other credentials through environment variables.

Before each table restore, the function reads the service accounts of the source and destination Cloud SQL instances and ensures they have `roles/storage.objectAdmin` on the backup bucket. This is required because the point-in-time clone is created at runtime and its Cloud SQL service account must be allowed to write the export file. The IAM policy update preserves existing bindings and retries concurrent policy changes.

## Runtime Configuration

The following runtime environment variables are required:

| Variable | Value |
| --- | --- |
| `PROJECT_ID` | GCP project ID containing the Cloud SQL instance. |
| `DEST_INSTANCE_NAME` | Cloud SQL instance name or connection name (`project:region:instance`). |
| `RESTORE_GCS_BUCKET` | Backup bucket name without the `gs://` prefix. |

The point-in-time restore source is the destination instance itself, so no separate source-instance variable is required. Authentication is provided by the function's attached runtime service account through Application Default Credentials.

Example Terraform configuration for a second-generation function:

```hcl
service_config {
  service_account_email = google_service_account.pitr.email
  timeout_seconds       = 3600

  environment_variables = {
    PROJECT_ID           = var.project_id
    DEST_INSTANCE_NAME   = google_sql_database_instance.blaise.connection_name
    RESTORE_GCS_BUCKET   = google_storage_bucket.backups.name
  }
}
```

## Invoke From GCP Console

After Terraform has deployed the function:

1. Open the function in the Google Cloud Console.
2. Open the testing or invoke view.
3. Enter the JSON request body shown below.
4. Invoke the function and wait for the restore to complete.

```json
{
  "table_name": "LMS2601_KX2",
  "timestamp": "2026-07-08 14:30:00",
  "database_name": "blaise"
}
```

The restore runs synchronously. Keep the Console request open until the function responds, and use the returned request ID to locate errors in Cloud Logging.

Enter `table_name` and `database_name` using the exact casing used by the active Cloud SQL instance; both identifiers are case-sensitive.

## Restore Flow

1. Validate and parse the request.
2. Read the destination database name from the request and the remaining Cloud SQL configuration supplied by Terraform.
3. Create a point-in-time clone.
4. Resolve the requested table names. For `blaise`, append `_Dml` and `_Form`; otherwise use `table_name` unchanged.
5. Export each resolved table from the clone to Cloud Storage and import it into the destination.
6. Delete the temporary clone, including when a restore step fails.

## Development

Install development dependencies with Poetry:

```bash
poetry install
```

Run the repository checks directly through Poetry:

```bash
poetry run ruff check .
poetry run pyright
poetry run deptry .
poetry run vulture .
poetry run pytest
```
