"""Read-only inspection of Supabase Data API role membership and privileges."""

from sqlalchemy import text


API_ROLES = ("anon", "authenticated", "service_role")
RUNTIME_ROLE = "finwise_runtime"

API_ROLE_SECURITY_QUERY = text(
    """
    SELECT
        api.rolname::text AS role_name,
        api.rolsuper AS is_superuser,
        api.rolbypassrls AS bypasses_rls,
        api.rolcanlogin AS can_login,
        has_schema_privilege(api.oid, 'public', 'USAGE') AS public_usage,
        has_schema_privilege(api.oid, 'public', 'CREATE') AS public_create,
        ARRAY(
            SELECT parent.rolname::text
            FROM pg_catalog.pg_auth_members membership
            JOIN pg_catalog.pg_roles parent ON parent.oid = membership.roleid
            WHERE membership.member = api.oid
            ORDER BY parent.rolname
        ) AS direct_memberships,
        ARRAY(
            SELECT candidate.rolname::text
            FROM pg_catalog.pg_roles candidate
            WHERE candidate.oid <> api.oid
              AND pg_has_role(api.oid, candidate.oid, 'MEMBER')
            ORDER BY candidate.rolname
        ) AS effective_memberships,
        ARRAY(
            SELECT member_role.rolname::text
            FROM pg_catalog.pg_auth_members membership
            JOIN pg_catalog.pg_roles member_role ON member_role.oid = membership.member
            WHERE membership.roleid = api.oid
            ORDER BY member_role.rolname
        ) AS direct_members
    FROM pg_catalog.pg_roles api
    WHERE api.rolname IN ('anon', 'authenticated', 'service_role')
    ORDER BY api.rolname
    """
)

RUNTIME_ROLE_QUERY = text(
    """
    SELECT
        runtime.rolname::text AS role_name,
        runtime.rolsuper AS is_superuser,
        runtime.rolbypassrls AS bypasses_rls,
        runtime.rolcreatedb AS can_create_database,
        runtime.rolcreaterole AS can_create_roles,
        runtime.rolcanlogin AS can_login,
        runtime.rolinherit AS inherits_privileges,
        pg_catalog.pg_get_userbyid(database.datdba) = runtime.rolname AS owns_database,
        has_schema_privilege(runtime.oid, 'public', 'USAGE') AS public_usage,
        has_schema_privilege(runtime.oid, 'public', 'CREATE') AS public_create,
        ARRAY(
            SELECT parent.rolname::text
            FROM pg_catalog.pg_auth_members membership
            JOIN pg_catalog.pg_roles parent ON parent.oid = membership.roleid
            WHERE membership.member = runtime.oid
            ORDER BY parent.rolname
        ) AS direct_memberships,
        ARRAY(
            SELECT candidate.rolname::text
            FROM pg_catalog.pg_roles candidate
            WHERE candidate.oid <> runtime.oid
              AND pg_has_role(runtime.oid, candidate.oid, 'MEMBER')
            ORDER BY candidate.rolname
        ) AS effective_memberships
    FROM pg_catalog.pg_roles runtime
    CROSS JOIN pg_catalog.pg_database database
    WHERE runtime.rolname = 'finwise_runtime'
      AND database.datname = current_database()
    """
)


def inspect_api_roles(connection) -> dict[str, dict | None]:
    """Return actual catalog findings; missing roles remain explicitly absent."""
    rows = connection.execute(API_ROLE_SECURITY_QUERY).mappings().all()
    found = {row["role_name"]: dict(row) for row in rows}
    return {role_name: found.get(role_name) for role_name in API_ROLES}


def inspect_runtime_role(connection) -> dict | None:
    """Return the actual runtime-role catalog row, or None when it is absent."""
    row = connection.execute(RUNTIME_ROLE_QUERY).mappings().one_or_none()
    return dict(row) if row is not None else None


def format_runtime_role_finding(finding: dict | None) -> str:
    """Report absence explicitly and never infer privileges for a missing role."""
    if finding is None:
        return f"runtime_role={RUNTIME_ROLE} status=ABSENT"
    return f"runtime_role={RUNTIME_ROLE} status=PRESENT attributes={finding}"


def format_api_role_findings(findings: dict[str, dict | None]) -> list[str]:
    """Format catalog findings without inferring state for absent roles."""
    output: list[str] = []
    for role_name in API_ROLES:
        finding = findings.get(role_name)
        if finding is None:
            output.append(f"api_role={role_name} status=ABSENT")
            continue
        output.append(
            f"api_role={role_name} status=PRESENT "
            f"is_superuser={finding['is_superuser']} "
            f"bypasses_rls={finding['bypasses_rls']} "
            f"can_login={finding['can_login']} "
            f"public_usage={finding['public_usage']} "
            f"public_create={finding['public_create']} "
            f"direct_memberships={finding['direct_memberships']} "
            f"effective_memberships={finding['effective_memberships']} "
            f"direct_members={finding['direct_members']}"
        )
    return output
