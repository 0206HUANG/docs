import uuid
from unittest.mock import MagicMock

import pytest

from app.core.permissions import assert_same_tenant, role_level, RoleName
from app.core.exceptions import PermissionError


def test_role_hierarchy():
    assert role_level(RoleName.SUPER_ADMIN) > role_level(RoleName.TENANT_ADMIN)
    assert role_level(RoleName.TENANT_ADMIN) > role_level(RoleName.DEPT_MANAGER)
    assert role_level(RoleName.DEPT_MANAGER) > role_level(RoleName.MEMBER)


def test_assert_same_tenant_passes():
    tid = uuid.uuid4()
    assert_same_tenant(tid, tid)  # should not raise


def test_assert_same_tenant_fails():
    with pytest.raises(PermissionError):
        assert_same_tenant(uuid.uuid4(), uuid.uuid4())


def test_unknown_role_has_zero_level():
    assert role_level("UNKNOWN_ROLE") == 0
