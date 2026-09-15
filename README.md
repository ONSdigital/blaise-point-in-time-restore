# Blaise Questionnaire Point-in-Time Restore

This repository contains the source for a deployable HTTP Google Cloud Function. The function restores questionnaire data to a specific point in time by creating a temporary Cloud SQL clone, exporting the questionnaire tables to Cloud Storage, and importing them into the live database.

The Cloud Function is intended to be packaged and deployed by Terraform maintained in a separate infrastructure repository. This repository does not create infrastructure or deploy itself.

## Function Contract

- Runtime: Python 3.13
- Entry point: `restore_point_in_time_questionnaire`
- Trigger: HTTP
- Request content type: `application/json`
- Maximum execution time: 3600 seconds
- Recommended memory: at least 512 MiB

The function expects this request body:

```json
{
   "questionnaire_name": "LMS2601_KX2",
   "timestamp": "2026-07-08 14:30:00"
}
```

`timestamp` is parsed as UK local time (`Europe/London`) when no timezone offset is supplied. An ISO 8601 timestamp with an explicit offset is also accepted.

Successful requests return HTTP `200`. Validation failures return HTTP `400`, and restore failures return HTTP `500` with a request ID that can be matched to Cloud Logging entries.

## What Gets Restored

The restore currently targets two tables per questionnaire:

- `<QUESTIONNAIRE_NAME>_Dml`
- `<QUESTIONNAIRE_NAME>_Form`

The destination tables are restored from SQL export files generated from the clone.

## Deployment

The Terraform deployment must package the repository root so that `main.py` and `requirements.txt` are at the root of the Cloud Function source archive.

The infrastructure must provide:

- A second-generation HTTP Cloud Function using the Python 3.13 runtime.
- A dedicated runtime service account.
- A VPC connector with access to the Cloud SQL instance.
- A timeout that accommodates the restore operation; 3600 seconds is recommended.
- Authentication on the HTTP endpoint. Do not allow unauthenticated invocation.
- Cloud SQL Admin, Secret Manager Secret Accessor, and Logs Writer permissions for the runtime service account.
- Cloud Storage access to the environment backup bucket for the runtime service account and the Cloud SQL instance service account.
- Cloud Run Invoker permission for operators who invoke the second-generation function.

The function uses Application Default Credentials from its runtime service account. It discovers the GCP project, the Blaise Cloud SQL instance, the database, and the backup bucket when handling restore work, after the Functions Framework has started.

## Runtime Configuration

No runtime environment variables are required.

The function discovers:

- The current project from Application Default Credentials.
- The destination Cloud SQL instance matching `blaise-<environment>-<id>`.
- The `blaise` database, or the only non-system database when there is one.
- The backup bucket as `ons-blaise-v2-<environment>-backups`.
- The source instance, which is the same as the destination instance before cloning.

The Cloud SQL password is read from the latest version of the `cloudsql_pw` Secret Manager secret.

## Invoke From GCP Console

After Terraform has deployed the function:

1. Open the function in the Google Cloud Console.
2. Open the testing or invoke view.
3. Enter the JSON request body shown below.
4. Invoke the function and wait for the restore to complete.

```json
{
  "questionnaire_name": "LMS2601_KX2",
  "timestamp": "2026-07-08 14:30:00"
}
```

The restore runs synchronously. Keep the Console request open until the function responds, and use the returned request ID to locate errors in Cloud Logging.

## Restore Flow

1. Validate and parse the request.
2. Discover the source and destination Cloud SQL configuration.
3. Create a point-in-time clone.
4. Export `<QUESTIONNAIRE>_Dml` from the clone to Cloud Storage and import it into the destination.
5. Export `<QUESTIONNAIRE>_Form` from the clone to Cloud Storage and import it into the destination.
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
