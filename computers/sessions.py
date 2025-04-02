from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import os
from typing import Any, BinaryIO, Callable, List, Literal, Optional, Tuple
from uuid import uuid4
from azure.identity import get_bearer_token_provider, DefaultAzureCredential
import urllib

import requests

USER_AGENT = "openai-cua-sample-app (python)"


@dataclass
class RemoteFileMetadata:
    """Metadata for a file in the session."""

    filename: str
    """The filename relative to `/mnt/data`."""

    size_in_bytes: int
    """The size of the file in bytes."""

    @property
    def full_path(self) -> str:
        """Get the full path of the file."""
        return f"/mnt/data/{self.filename}"

    @staticmethod
    def from_dict(data: dict) -> "RemoteFileMetadata":
        """Create a RemoteFileMetadata object from a dictionary."""
        properties = data.get("properties", {})
        return RemoteFileMetadata(
            filename=properties.get("filename"),
            size_in_bytes=properties.get("size"),
        )


def _default_token_provider(self) -> Optional[str]:
    return get_bearer_token_provider(DefaultAzureCredential(), 'https://dynamicsessions.io/.default')()


class CodeInterpreterSession:

    sanitize_input: bool = True
    """Whether to sanitize input to the python REPL."""

    pool_management_endpoint: str
    """The management endpoint of the session pool. Should end with a '/'."""

    access_token_provider: Callable[[], Optional[str]] = _default_token_provider
    """A function that returns the access token to use for the session pool."""

    session_id: str = str(uuid4())
    """The session ID to use for the code interpreter. Defaults to a random UUID."""


    def __init__(
        self,
        pool_management_endpoint: str,
    ):
        """Initialize the CodeInterpreterSession.

        Args:
            pool_management_endpoint (str): The management endpoint of the session pool.
                Should end with a '/'.
        """
        if pool_management_endpoint:
            self.pool_management_endpoint = pool_management_endpoint
        else:
            self.pool_management_endpoint = os.getenv("POOL_MANAGEMENT_ENDPOINT")

        if not self.pool_management_endpoint:
            raise ValueError("pool_management_endpoint is not set")
        

    def _build_url(self, path: str) -> str:
        pool_management_endpoint = self.pool_management_endpoint
        if not pool_management_endpoint:
            raise ValueError("pool_management_endpoint is not set")
        if not pool_management_endpoint.endswith("/"):
            pool_management_endpoint += "/"
        encoded_session_id = urllib.parse.quote(self.session_id)
        query = f"identifier={encoded_session_id}&api-version=2024-02-02-preview"
        query_separator = "&" if "?" in pool_management_endpoint else "?"
        full_url = pool_management_endpoint + path + query_separator + query
        return full_url


    def execute(self, python_code: str) -> Any:
        """Execute Python code in the session."""

        print(f"--------\nExecuting code:\n{python_code}\n--------")

        access_token = self.access_token_provider()
        api_url = self._build_url("code/execute")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        body = {
            "properties": {
                "codeInputType": "inline",
                "executionType": "synchronous",
                "code": python_code,
            }
        }

        response = requests.post(api_url, headers=headers, json=body)
        response.raise_for_status()
        response_json = response.json()
        properties = response_json.get("properties", {})
        # print(f"--------\nResponse:\n{properties}\n--------")
        return properties


    def upload_file(
        self,
        *,
        data: Optional[BinaryIO] = None,
        remote_file_path: Optional[str] = None,
        local_file_path: Optional[str] = None,
    ) -> RemoteFileMetadata:
        """Upload a file to the session.

        Args:
            data: The data to upload.
            remote_file_path: The path to upload the file to, relative to
                `/mnt/data`. If local_file_path is provided, this is defaulted
                to its filename.
            local_file_path: The path to the local file to upload.

        Returns:
            RemoteFileMetadata: The metadata for the uploaded file
        """
        if data and local_file_path:
            raise ValueError("data and local_file_path cannot be provided together")

        if data:
            file_data = data
        elif local_file_path:
            if not remote_file_path:
                remote_file_path = os.path.basename(local_file_path)
            file_data = open(local_file_path, "rb")

        access_token = self.access_token_provider()
        api_url = self._build_url("files/upload")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }
        files = [("file", (remote_file_path, file_data, "application/octet-stream"))]

        response = requests.request(
            "POST", api_url, headers=headers, data={}, files=files
        )
        response.raise_for_status()

        response_json = response.json()
        return RemoteFileMetadata.from_dict(response_json["value"][0])


    def download_file(
        self, *, remote_file_path: str, local_file_path: Optional[str] = None
    ) -> BinaryIO:
        """Download a file from the session.

        Args:
            remote_file_path: The path to download the file from,
                relative to `/mnt/data`.
            local_file_path: The path to save the downloaded file to.
                If not provided, the file is returned as a BufferedReader.

        Returns:
            BinaryIO: The data of the downloaded file.
        """
        access_token = self.access_token_provider()
        encoded_remote_file_path = urllib.parse.quote(remote_file_path)
        api_url = self._build_url(f"files/content/{encoded_remote_file_path}")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }

        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        if local_file_path:
            with open(local_file_path, "wb") as f:
                f.write(response.content)

        return BytesIO(response.content)


    def list_files(self) -> List[RemoteFileMetadata]:
        """List the files in the session.

        Returns:
            list[RemoteFileMetadata]: The metadata for the files in the session
        """
        access_token = self.access_token_provider()
        api_url = self._build_url("files")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }

        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        response_json = response.json()
        return [RemoteFileMetadata.from_dict(entry) for entry in response_json["value"]]
    