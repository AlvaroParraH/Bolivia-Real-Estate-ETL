from __future__ import annotations

import os
from pathlib import Path


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
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise RuntimeError(
            "azure-storage-blob is not installed. Install dependencies before using --upload-azure."
        ) from exc

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise RuntimeError(
            "Missing AZURE_STORAGE_CONNECTION_STRING environment variable."
        )

    if not container_name:
        raise RuntimeError(
            "Missing Azure container name. Set --azure-container or AZURE_STORAGE_CONTAINER."
        )

    service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = service_client.get_container_client(container_name)

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