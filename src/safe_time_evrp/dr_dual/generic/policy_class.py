"""Declared restricted policy class shared by exact oracle and online solver."""

from __future__ import annotations

# First travel (any free vehicle) + common nonanticipative continuation of this length.
RESTRICTED_CONTINUATION_MAX_LEN = 6
RESTRICTED_CONTINUATION_MAX_BRANCH = 6
RESTRICTED_PLAN_CAP = 500
