from scripts.postgres_role_inspection import (
    API_ROLES,
    API_ROLE_SECURITY_QUERY,
    format_api_role_findings,
    format_runtime_role_finding,
    inspect_api_roles,
    inspect_runtime_role,
    RUNTIME_ROLE_QUERY,
)


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def one_or_none(self):
        return self._rows[0] if self._rows else None


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return _Mappings(self._rows)


class _ReadOnlyConnection:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def execute(self, statement):
        self.statements.append(str(statement))
        return _Result(self.rows)


def test_inspection_reports_absent_roles_without_inventing_privileges_or_memberships():
    connection = _ReadOnlyConnection(
        [
            {
                "role_name": "authenticated",
                "is_superuser": False,
                "bypasses_rls": False,
                "can_login": False,
                "public_usage": True,
                "public_create": False,
                "direct_memberships": [],
                "effective_memberships": [],
                "direct_members": ["authenticator"],
            }
        ]
    )

    findings = inspect_api_roles(connection)
    output = "\n".join(format_api_role_findings(findings))

    assert tuple(findings) == API_ROLES
    assert findings["anon"] is None
    assert findings["authenticated"]["public_create"] is False
    assert findings["service_role"] is None
    assert "api_role=anon status=ABSENT" in output
    assert "api_role=service_role status=ABSENT" in output
    assert "api_role=authenticated status=PRESENT" in output
    assert "direct_members=['authenticator']" in output
    assert "api_role=anon status=PRESENT" not in output


def test_inspection_queries_effective_create_and_direct_and_inherited_memberships():
    connection = _ReadOnlyConnection([])
    inspect_api_roles(connection)

    statement = connection.statements[0]
    assert "has_schema_privilege(api.oid, 'public', 'CREATE')" in statement
    assert "pg_auth_members" in statement
    assert "pg_has_role(api.oid, candidate.oid, 'MEMBER')" in statement


def test_runtime_role_inspection_reports_absence_without_inferred_privileges():
    connection = _ReadOnlyConnection([])

    finding = inspect_runtime_role(connection)

    assert finding is None
    assert format_runtime_role_finding(finding) == (
        "runtime_role=finwise_runtime status=ABSENT"
    )
    assert "owns_database" in connection.statements[0]
    assert "has_schema_privilege(runtime.oid, 'public', 'CREATE')" in connection.statements[0]


def test_runtime_role_inspection_formats_actual_memberships_and_flags():
    attributes = {
        "role_name": "finwise_runtime",
        "is_superuser": False,
        "bypasses_rls": False,
        "can_create_database": False,
        "can_create_roles": False,
        "can_login": True,
        "inherits_privileges": True,
        "owns_database": False,
        "public_usage": True,
        "public_create": False,
        "direct_memberships": ["finwise_backend"],
        "effective_memberships": ["finwise_backend"],
    }
    connection = _ReadOnlyConnection([attributes])

    finding = inspect_runtime_role(connection)
    output = format_runtime_role_finding(finding)

    assert finding == attributes
    assert "bypasses_rls': False" in output
    assert "direct_memberships': ['finwise_backend']" in output
    assert "effective_memberships': ['finwise_backend']" in output
    assert "runtime.rolinherit" in str(RUNTIME_ROLE_QUERY)
