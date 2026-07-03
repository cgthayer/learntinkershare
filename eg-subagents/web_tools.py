"""Web tools handed to sub-agents. Kept deliberately small and side-effect free."""

import logging

import html2text
import requests
from smolagents import tool

logger = logging.getLogger(__name__)

# Cap on characters returned to a sub-agent so a single huge page cannot blow up
# its context window. The manager never sees this content at all.
MAX_PAGE_CHARS = 12_000


@tool
def visit_webpage(url: str) -> str:
    """Fetch a web page and return its content as Markdown.

    Args:
        url: The URL of the page to fetch.

    Returns:
        The page content converted to Markdown (truncated if very long),
        or an error string if the request fails.
    """
    logger.info("visit_webpage url=%s", url)
    try:
        headers = {"User-Agent": "eg-subagents/1.0 (smolagents demo)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:  # noqa: BLE001 - expected failure, report it to the agent
        logger.exception("visit_webpage failed url=%s", url)
        return f"<error fetching {url}: {e}>"

    markdown = html_to_markdown(response.text)
    if len(markdown) > MAX_PAGE_CHARS:
        return markdown[:MAX_PAGE_CHARS] + "\n\n<...truncated...>"
    return markdown


@tool
def html_to_markdown(html: str) -> str:
    """Convert an HTML string to Markdown.

    Args:
        html: The HTML content to convert.

    Returns:
        The Markdown representation of the input HTML.
    """
    if not html:
        return ""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.body_width = 0
    return converter.handle(html)
