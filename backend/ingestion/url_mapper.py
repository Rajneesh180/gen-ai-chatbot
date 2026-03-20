"""
Map repo-relative file paths to their public GitLab URLs.

Handbook pages live under handbook.gitlab.com, direction pages under
about.gitlab.com.  The mapping strips the local repo prefix, removes
file extensions, and normalises _index files to directory URLs.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Base URLs
# ---------------------------------------------------------------------------

_HANDBOOK_BASE = "https://handbook.gitlab.com"
_DIRECTION_BASE = "https://about.gitlab.com"

# ---------------------------------------------------------------------------
# Extension patterns (order matters — longest first)
# ---------------------------------------------------------------------------

_DIRECTION_EXTS = re.compile(r"\.(html\.md\.erb|html\.md|md)$")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def map_file_path_to_url(file_path: str, source_type: str) -> str:
    """Convert a repo-relative *file_path* to its public URL.

    Parameters
    ----------
    file_path : str
        Path relative to the cloned repo root, forward-slash separated.
        Examples: ``content/handbook/values/_index.md``,
        ``source/direction/create/_index.html.md.erb``.
    source_type : str
        ``"handbook"`` or ``"direction"``.

    Returns
    -------
    str
        Fully-qualified URL with trailing slash, or ``""`` if
        *source_type* is unrecognised.
    """
    # normalise backslashes (Windows edge case)
    file_path = file_path.replace("\\", "/")

    if source_type == "handbook":
        return _map_handbook(file_path)
    if source_type == "direction":
        return _map_direction(file_path)
    return ""


# ---------------------------------------------------------------------------
# Handbook / TeamOps mapping
# ---------------------------------------------------------------------------

def _map_handbook(file_path: str) -> str:
    """Handbook and TeamOps pages → handbook.gitlab.com.

    Rules
    -----
    content/handbook/{path}/_index.md   → /handbook/{path}/
    content/handbook/{path}/name.md     → /handbook/{path}/name/
    content/teamops/{path}/_index.md    → /teamops/{path}/
    content/teamops/{path}/name.md      → /teamops/{path}/name/
    """
    # strip the leading "content/" prefix
    url_path = re.sub(r"^content/", "", file_path)

    # strip _index.md → treat as directory
    url_path = re.sub(r"/_index\.md$", "/", url_path)

    # strip other .md filenames → keep the stem as a path segment
    url_path = re.sub(r"\.md$", "/", url_path)

    # ensure single trailing slash, no double slashes
    url_path = url_path.rstrip("/") + "/"

    return f"{_HANDBOOK_BASE}/{url_path}"


# ---------------------------------------------------------------------------
# Direction mapping
# ---------------------------------------------------------------------------

def _map_direction(file_path: str) -> str:
    """Direction pages → about.gitlab.com.

    Rules
    -----
    source/direction/{path}/_index.html.md.erb → /direction/{path}/
    source/direction/{path}/name.html.md.erb   → /direction/{path}/name/
    source/direction/{path}/name.html.md       → /direction/{path}/name/
    source/direction/{path}/name.md            → /direction/{path}/name/
    """
    # strip leading "source/" prefix
    url_path = re.sub(r"^source/", "", file_path)

    # strip _index + any extension combo → treat as directory
    url_path = re.sub(r"/_index(?:\.html\.md\.erb|\.html\.md|\.md)$", "/", url_path)

    # strip remaining multi-part extensions
    url_path = _DIRECTION_EXTS.sub("/", url_path)

    # normalise slashes
    url_path = url_path.rstrip("/") + "/"

    return f"{_DIRECTION_BASE}/{url_path}"
