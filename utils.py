import datetime
import os
import requests
from dotenv import load_dotenv
import json
import base64
from PIL import Image
from io import BytesIO
import io
from urllib.parse import urlparse
from pathlib import Path

load_dotenv(override=True)
# Load .env.secret from the parent folder
parent_dir = Path(__file__).parent.parent
secret_env_path = parent_dir / ".env.secret"
if secret_env_path.exists():
    load_dotenv(dotenv_path=secret_env_path, override=True)

BLOCKED_DOMAINS = [
    "maliciousbook.com",
    "evilvideos.com",
    "darkwebforum.com",
    "shadytok.com",
    "suspiciouspins.com",
    "ilanbigio.com",
]


def pp(obj):
    print(json.dumps(obj, indent=4))


def show_image(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(BytesIO(image_data))
    image.show()


def calculate_image_dimensions(base_64_image):
    image_data = base64.b64decode(base_64_image)
    image = Image.open(io.BytesIO(image_data))
    return image.size


def sanitize_message(msg: dict) -> dict:
    """Return a copy of the message with image_url omitted for computer_call_output messages."""
    if msg.get("type") == "computer_call_output":
        output = msg.get("output", {})
        if isinstance(output, dict):
            sanitized = msg.copy()
            sanitized["output"] = {**output, "image_url": "[omitted]"}
            return sanitized
    return msg


def create_response(**kwargs):
    azure_openai_api_base = os.getenv("AZURE_OPENAI_API_BASE")
    url = f"{azure_openai_api_base}openai/responses?api-version=2025-03-01-preview"
    headers = {
        "Api-key": os.getenv('AZURE_OPENAI_API_KEY'),
        "Content-Type": "application/json"
    }

    openai_org = os.getenv("OPENAI_ORG")
    if openai_org:
        headers["Openai-Organization"] = openai_org

    response = requests.post(url, headers=headers, json=kwargs)

    if response.status_code != 200:
        print(f"Error: {response.status_code} {response.text}")

    response_json = response.json()
    # print(f"Response: {response_json}")
    return response_json


def check_blocklisted_url(url: str) -> None:
    """Raise ValueError if the given URL (including subdomains) is in the blocklist."""
    hostname = urlparse(url).hostname or ""
    if any(
        hostname == blocked or hostname.endswith(f".{blocked}")
        for blocked in BLOCKED_DOMAINS
    ):
        raise ValueError(f"Blocked URL: {url}")


class HtmlLogger:
    """
    A logger that writes HTML to a file.
    """

    LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

    HTML_TEMPLATE = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Log</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                font-size: 1.5em;
            }}
        </style>
        <script>
            document.addEventListener("DOMContentLoaded", function() {{
                window.scrollTo(0, document.body.scrollHeight);
            }});
        </script>
    </head>
    <body>
        {content}
    </body>
    </html>
    """

    def __init__(self, filename: str):
        self.filename = filename
        self.html = ""

    def _timestamp_str(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, message: str):
        self.html += f"\n<hr /><p>{self._timestamp_str()}<br />{message}</p>"
        self.save()

    def log_image(self, image_base64: str):
        self.html += f'\n<hr /><p>{self._timestamp_str()}<br /><img src="data:image/png;base64,{image_base64}" alt="Screenshot" /></p>'

    def save(self):
        os.makedirs(self.LOG_DIR, exist_ok=True)
        with open(os.path.join(self.LOG_DIR, self.filename), "w") as f:
            f.write(self.HTML_TEMPLATE.format(content=self.html))