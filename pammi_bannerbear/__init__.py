"""pammi_bannerbear - Bannerbear API client skeleton.

Bannerbear is a transactional image/video API. We use it to render
branded templates (concept cards, quote cards, etc.) via template IDs.

This is a STUB. The actual API key is not yet configured. Once the user
provides BANNERBEAR_API_KEY, the client will be ready to use.

API docs: https://developers.bannerbear.com/

Setup:
    1. Sign up at https://www.bannerbear.com/
    2. Get an API key from https://app.bannerbear.com/
    3. Set environment variable: export BANNERBEAR_API_KEY=...
    4. Create templates in the Bannerbear dashboard
    5. Use template IDs when calling create_image()

Common workflow:
    bb = BannerbearClient()
    if not bb.is_configured():
        raise RuntimeError("BANNERBEAR_API_KEY not set")
    result = bb.create_image(
        template_id="abc123",
        modifications=[{"name": "title", "text": "My Title"}],
    )
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "API_BASE_URL",
    "ENV_VAR",
    "BannerbearError",
    "BannerbearClient",
    "create_image",
    "create_video",
    "get_template",
    "is_configured",
    "main",
]

API_BASE_URL = "https://api.bannerbear.com/v2"
ENV_VAR = "BANNERBEAR_API_KEY"


class BannerbearError(Exception):
    """Raised when Bannerbear API returns an error."""
    pass


def is_configured() -> bool:
    """Check if the BANNERBEAR_API_KEY environment variable is set."""
    return bool(os.environ.get(ENV_VAR))


def _get_api_key() -> str:
    """Get the API key from env vars. Raises if not set."""
    key = os.environ.get(ENV_VAR)
    if not key:
        raise BannerbearError(
            f"BANNERBEAR_API_KEY environment variable is not set. "
            f"Get a key from https://app.bannerbear.com/ and "
            f"run: export {ENV_VAR}=your_key_here"
        )
    return key


def _api_request(method: str, endpoint: str, payload: Optional[dict] = None,
                 timeout: int = 30) -> dict:
    """Make a Bannerbear API request."""
    api_key = _get_api_key()
    url = f"{API_BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = json.loads(body)
        except json.JSONDecodeError:
            err = {"raw": body}
        raise BannerbearError(f"Bannerbear API error {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise BannerbearError(f"Failed to reach Bannerbear: {e.reason}") from e


class BannerbearClient:
    """Client for the Bannerbear API.

    Example:
        >>> bb = BannerbearClient()
        >>> if not bb.is_configured():
        ...     print("API key not set")
        ...     return
        >>> result = bb.create_image(
        ...     template_id="abc123",
        ...     modifications=[
        ...         {"name": "title", "text": "Hello"},
        ...         {"name": "subtitle", "text": "World"},
        ...     ],
        ... )
        >>> print(result["image_url"])
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = API_BASE_URL):
        """Initialize the client.

        Args:
            api_key: API key. Defaults to BANNERBEAR_API_KEY env var.
            base_url: Override API base URL (for testing).
        """
        self.api_key = api_key
        self.base_url = base_url
        # Set env var so _api_request picks it up
        if api_key is not None:
            os.environ[ENV_VAR] = api_key

    def is_configured(self) -> bool:
        """Check if the API key is set."""
        return bool(self.api_key or is_configured())

    def list_templates(self) -> list[dict]:
        """List all available templates in the account."""
        result = _api_request("GET", "/templates")
        return result if isinstance(result, list) else result.get("templates", [])

    def get_template(self, template_id: str) -> dict:
        """Get details of a specific template."""
        return _api_request("GET", f"/templates/{template_id}")

    def create_image(self, template_id: str,
                     modifications: list[dict],
                     webhook_url: Optional[str] = None,
                     metadata: Optional[dict] = None,
                     sync: bool = True) -> dict:
        """Create an image from a template.

        Args:
            template_id: The Bannerbear template ID.
            modifications: List of modifications, e.g.
                [{"name": "title", "text": "Hello"}]
            webhook_url: Optional URL to POST when rendering completes.
            metadata: Optional metadata to attach to the request.
            sync: If True, wait for rendering to complete before returning.

        Returns:
            Dict with at least: uid, image_url, status.
        """
        payload = {
            "template": template_id,
            "modifications": modifications,
        }
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if metadata is not None:
            payload["metadata"] = metadata

        result = _api_request("POST", "/images", payload)

        if sync and result.get("status") != "completed":
            # Poll until complete
            import time
            uid = result.get("uid")
            if uid:
                for _ in range(60):  # Max 60 seconds
                    time.sleep(1)
                    result = _api_request("GET", f"/images/{uid}")
                    if result.get("status") == "completed":
                        break
                    if result.get("status") == "failed":
                        raise BannerbearError(
                            f"Bannerbear rendering failed: {result.get('message', 'unknown error')}"
                        )

        return result

    def create_video(self, template_id: str,
                     modifications: list[dict],
                     webhook_url: Optional[str] = None,
                     metadata: Optional[dict] = None,
                     sync: bool = True,
                     input_media_url: Optional[str] = None) -> dict:
        """Create a video from a template.

        Args:
            template_id: The Bannerbear video template ID.
            modifications: List of modifications.
            webhook_url: Optional URL to POST when rendering completes.
            metadata: Optional metadata.
            sync: If True, wait for rendering to complete.
            input_media_url: Optional source video for animated templates.

        Returns:
            Dict with at least: uid, video_url, status.
        """
        payload = {
            "template": template_id,
            "modifications": modifications,
        }
        if webhook_url is not None:
            payload["webhook_url"] = webhook_url
        if metadata is not None:
            payload["metadata"] = metadata
        if input_media_url is not None:
            payload["input_media_url"] = input_media_url

        result = _api_request("POST", "/videos", payload)

        if sync and result.get("status") != "completed":
            import time
            uid = result.get("uid")
            if uid:
                for _ in range(300):  # Max 5 minutes
                    time.sleep(2)
                    result = _api_request("GET", f"/videos/{uid}")
                    if result.get("status") == "completed":
                        break
                    if result.get("status") == "failed":
                        raise BannerbearError(
                            f"Bannerbear video rendering failed: {result.get('message', 'unknown error')}"
                        )

        return result


# Module-level convenience functions
def create_image(template_id: str, modifications: list[dict], **kwargs) -> dict:
    """Create an image using the default client."""
    bb = BannerbearClient()
    return bb.create_image(template_id, modifications, **kwargs)


def create_video(template_id: str, modifications: list[dict], **kwargs) -> dict:
    """Create a video using the default client."""
    bb = BannerbearClient()
    return bb.create_video(template_id, modifications, **kwargs)


def get_template(template_id: str) -> dict:
    """Get template details using the default client."""
    bb = BannerbearClient()
    return bb.get_template(template_id)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-bannerbear",
        description="Pammi Bannerbear - render branded templates (STUB - needs BANNERBEAR_API_KEY)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # status command
    status_parser = subparsers.add_parser("status", help="Check if API key is configured")

    # list command
    list_parser = subparsers.add_parser("list", help="List templates")

    # get command
    get_parser = subparsers.add_parser("get", help="Get template details")
    get_parser.add_argument("--template-id", required=True)

    # create-image command
    img_parser = subparsers.add_parser("create-image", help="Create an image")
    img_parser.add_argument("--template-id", required=True)
    img_parser.add_argument(
        "--modifications", "-m",
        required=True,
        help='Modifications as JSON, e.g. \'[{"name":"title","text":"X"}]\'',
    )
    img_parser.add_argument("--output", "-o", help="Output file path (downloads the image)")
    img_parser.add_argument("--no-sync", action="store_true", help="Don't wait for completion")

    # create-video command
    vid_parser = subparsers.add_parser("create-video", help="Create a video")
    vid_parser.add_argument("--template-id", required=True)
    vid_parser.add_argument("--modifications", "-m", required=True)
    vid_parser.add_argument("--output", "-o", help="Output file path")
    vid_parser.add_argument("--no-sync", action="store_true")

    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            if is_configured():
                print("✓ BANNERBEAR_API_KEY is configured")
                # Try to verify
                try:
                    bb = BannerbearClient()
                    templates = bb.list_templates()
                    print(f"  Account has {len(templates)} template(s)")
                    return 0
                except BannerbearError as e:
                    print(f"  But API call failed: {e}")
                    return 1
            else:
                print(f"✗ {ENV_VAR} is NOT set")
                print("  Set with: export BANNERBEAR_API_KEY=your_key_here")
                print("  Get a key from: https://app.bannerbear.com/")
                return 1
        elif args.command == "list":
            bb = BannerbearClient()
            templates = bb.list_templates()
            print(json.dumps(templates, indent=2))
            return 0
        elif args.command == "get":
            bb = BannerbearClient()
            template = bb.get_template(args.template_id)
            print(json.dumps(template, indent=2))
            return 0
        elif args.command == "create-image":
            modifications = json.loads(args.modifications)
            bb = BannerbearClient()
            result = bb.create_image(
                template_id=args.template_id,
                modifications=modifications,
                sync=not args.no_sync,
            )
            print(json.dumps(result, indent=2))
            if args.output and result.get("image_url"):
                _download_file(result["image_url"], args.output)
                print(f"\nSaved to: {args.output}")
            return 0
        elif args.command == "create-video":
            modifications = json.loads(args.modifications)
            bb = BannerbearClient()
            result = bb.create_video(
                template_id=args.template_id,
                modifications=modifications,
                sync=not args.no_sync,
            )
            print(json.dumps(result, indent=2))
            if args.output and result.get("video_url"):
                _download_file(result["video_url"], args.output)
                print(f"\nSaved to: {args.output}")
            return 0
        else:
            parser.print_help()
            return 1
    except BannerbearError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON for modifications: {e}", file=sys.stderr)
        return 1


def _download_file(url: str, output_path: str) -> None:
    """Download a file from a URL to a local path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as resp:
        output_path.write_bytes(resp.read())


if __name__ == "__main__":
    sys.exit(main())
