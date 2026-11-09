# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""TenantContext — REM-P0-02 foundation.

Every repository, cache key, and Temporal call must carry an explicit firm scope.
RLS (`SET LOCAL app.firm_id`) lands with migrations before Stage 4 evidence writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class TenantIsolationError(PermissionError):
    """Raised when a firm boundary would be crossed."""


Role = Literal["owner", "admin", "partner", "analyst", "operator", "demo"]


@dataclass(frozen=True, slots=True)
class TenantContext:
    firm_id: str
    user_id: str
    roles: tuple[str, ...]
    deal_team_assessment_ids: frozenset[str] = frozenset()
    is_demo_session: bool = False

    def assert_firm(self, firm_id: str) -> None:
        if firm_id != self.firm_id:
            raise TenantIsolationError(
                f"firm mismatch: context={self.firm_id} resource={firm_id}"
            )

    def may_access_private(self, assessment_id: str) -> bool:
        """Deal-team membership required for private evidence (D1 / data room)."""
        return assessment_id in self.deal_team_assessment_ids
