from __future__ import annotations

import os
from pathlib import Path


def _sanitize_sas_token(token: str | None) -> str | None:
    if not token:
        return None
    clean = token.strip()
    if clean.startswith("?"):
        clean = clean[1:]
    return clean or None


def _normalize_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""
    return prefix.strip().strip("/")


def upload_files_to_azure_blob(
    *,
    file_paths: list[Path],
    container_name: str,
    prefix: str | None = None,
    overwrite: bool = True,
) -> list[str]:
    try:
        from azure.storage.blob import BlobServiceClient, ContainerClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-storage-blob is not installed. Install dependencies before using --upload-azure."
        ) from exc

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    container_sas_url = os.getenv("AZURE_STORAGE_CONTAINER_SAS_URL", "").strip()
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "").strip()
    sas_token = _sanitize_sas_token(os.getenv("AZURE_STORAGE_SAS_TOKEN"))

    container_client: ContainerClient
    should_try_create_container = False

    if connection_string:
        if not container_name:
            raise RuntimeError(
                "Missing Azure container name. Set --azure-container or AZURE_STORAGE_CONTAINER."
            )
        service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = service_client.get_container_client(container_name)
        should_try_create_container = True
    elif container_sas_url:
        container_client = ContainerClient.from_container_url(container_sas_url)
    elif account_url and sas_token:
        if not container_name:
            raise RuntimeError(
                "Missing Azure container name. Set --azure-container or AZURE_STORAGE_CONTAINER."
            )
        service_client = BlobServiceClient(account_url=account_url, credential=sas_token)
        container_client = service_client.get_container_client(container_name)
    else:
        raise RuntimeError(
            "Missing Azure credentials. Set one of: AZURE_STORAGE_CONNECTION_STRING, "
            "AZURE_STORAGE_CONTAINER_SAS_URL, or AZURE_STORAGE_ACCOUNT_URL + AZURE_STORAGE_SAS_TOKEN."
        )

    if should_try_create_container:
        try:
            container_client.create_container()
        except Exception:
            # The container already exists in most runs. Any auth errors will surface on upload.
            pass

    clean_prefix = _normalize_prefix(prefix)
    uploaded_urls: list[str] = []

    for path in file_paths:
        blob_name = path.name
        if clean_prefix:
            blob_name = f"{clean_prefix}/{blob_name}"

        blob_client = container_client.get_blob_client(blob_name)
        with path.open("rb") as handle:
            blob_client.upload_blob(handle, overwrite=overwrite)
        uploaded_urls.append(blob_client.url)

    return uploaded_urls