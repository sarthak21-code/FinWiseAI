"""Remove Supabase Data API access to Alembic's control table.

The exact direct API-role grants are recorded in a private schema so the
downgrade can restore those pre-migration ACL edges. PUBLIC and owner ACLs are
left untouched; effective privilege checks fail the migration if PUBLIC still
exposes the table. The table owner is not changed and its privileges are never
revoked.
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_alembic_api_acl"
down_revision = "0003_postgres_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            alembic_owner text;
            public_owner text;
            database_owner text;
            api_role text;
        BEGIN
            IF current_database() <> 'postgres' OR current_user <> 'postgres' THEN
                RAISE EXCEPTION
                    'ACL correction requires the verified postgres database and postgres migration role';
            END IF;
            SELECT pg_catalog.pg_get_userbyid(datdba)
              INTO database_owner
              FROM pg_catalog.pg_database
             WHERE datname = current_database();
            IF database_owner <> current_user THEN
                RAISE EXCEPTION 'ACL correction requires the current role to own the database';
            END IF;
            SELECT pg_catalog.pg_get_userbyid(nspowner)
              INTO public_owner
              FROM pg_catalog.pg_namespace
             WHERE nspname = 'public';
            IF public_owner IS NULL OR public_owner <> 'pg_database_owner' THEN
                RAISE EXCEPTION 'public schema owner differs from the reviewed Supabase target';
            END IF;
            SELECT pg_catalog.pg_get_userbyid(c.relowner)
              INTO alembic_owner
              FROM pg_catalog.pg_class c
             WHERE c.oid = to_regclass('public.alembic_version');

            IF alembic_owner IS NULL OR alembic_owner <> current_user THEN
                RAISE EXCEPTION
                    'alembic_version ACL correction requires the current role to own the table';
            END IF;

            FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = api_role) THEN
                    RAISE EXCEPTION 'required Supabase API role % is absent', api_role;
                END IF;
            END LOOP;

            IF EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_class c
                  CROSS JOIN LATERAL pg_catalog.aclexplode(
                      COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
                  ) acl_item
                  JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl_item.grantee
                  JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl_item.grantor
                 WHERE c.oid = to_regclass('public.alembic_version')
                   AND grantee.rolname IN ('anon', 'authenticated', 'service_role')
                   AND grantor.rolname <> current_user
            ) THEN
                RAISE EXCEPTION
                    'alembic_version has API-role grants from another grantor; refusing incomplete ACL snapshot';
            END IF;
            IF EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_attribute a
                  CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) acl_item
                  JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl_item.grantee
                  JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl_item.grantor
                 WHERE a.attrelid = to_regclass('public.alembic_version')
                   AND a.attnum > 0
                   AND NOT a.attisdropped
                   AND a.attacl IS NOT NULL
                   AND pg_catalog.cardinality(a.attacl) > 0
                   AND grantee.rolname IN ('anon', 'authenticated', 'service_role')
                   AND grantor.rolname <> current_user
            ) THEN
                RAISE EXCEPTION
                    'alembic_version has API-role column grants from another grantor; refusing incomplete ACL snapshot';
            END IF;
        END
        $$;
        """
    )
    op.execute("CREATE SCHEMA finwise_migration_private")
    op.execute(
        "REVOKE ALL ON SCHEMA finwise_migration_private FROM PUBLIC, anon, authenticated, service_role"
    )
    op.create_table(
        "alembic_version_acl_snapshot",
        # This table stores only prior ACL edges, not application data.
        sa.Column("object_kind", sa.Text(), primary_key=True),
        sa.Column("column_name", sa.Text(), primary_key=True, server_default=""),
        sa.Column("grantee", sa.Text(), primary_key=True),
        sa.Column("grantor", sa.Text(), primary_key=True),
        sa.Column("privilege_type", sa.Text(), primary_key=True),
        sa.Column("is_grantable", sa.Boolean(), primary_key=True),
        schema="finwise_migration_private",
    )
    op.execute(
        "REVOKE ALL ON TABLE finwise_migration_private.alembic_version_acl_snapshot "
        "FROM PUBLIC, anon, authenticated, service_role"
    )
    op.execute(
        """
        INSERT INTO finwise_migration_private.alembic_version_acl_snapshot
            (object_kind, column_name, grantee, grantor, privilege_type, is_grantable)
        SELECT 'TABLE', '',
               CASE WHEN acl_item.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
               grantor.rolname,
               acl_item.privilege_type,
               acl_item.is_grantable
          FROM pg_catalog.pg_class c
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(c.relacl, pg_catalog.acldefault('r', c.relowner))
          ) acl_item
          LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl_item.grantee
          JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl_item.grantor
         WHERE c.oid = to_regclass('public.alembic_version')
           AND grantee.rolname IN ('anon', 'authenticated', 'service_role')
           AND grantor.rolname = current_user
        UNION ALL
        SELECT 'COLUMN', a.attname,
               CASE WHEN acl_item.grantee = 0 THEN 'PUBLIC' ELSE grantee.rolname END,
               grantor.rolname,
               acl_item.privilege_type,
               acl_item.is_grantable
          FROM pg_catalog.pg_attribute a
          CROSS JOIN LATERAL pg_catalog.aclexplode(a.attacl) acl_item
          LEFT JOIN pg_catalog.pg_roles grantee ON grantee.oid = acl_item.grantee
          JOIN pg_catalog.pg_roles grantor ON grantor.oid = acl_item.grantor
         WHERE a.attrelid = to_regclass('public.alembic_version')
           AND a.attnum > 0
           AND NOT a.attisdropped
           AND a.attacl IS NOT NULL
           AND pg_catalog.cardinality(a.attacl) > 0
           AND grantee.rolname IN ('anon', 'authenticated', 'service_role')
           AND grantor.rolname = current_user
        """
    )
    op.execute(
        "REVOKE ALL PRIVILEGES ON TABLE public.alembic_version "
        "FROM anon, authenticated, service_role"
    )
    op.execute(
        "REVOKE ALL (version_num) ON TABLE public.alembic_version "
        "FROM anon, authenticated, service_role"
    )
    op.execute(
        """
        DO $$
        DECLARE
            api_role text;
        BEGIN
            FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF has_table_privilege(api_role, 'public.alembic_version', 'SELECT')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'INSERT')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'UPDATE')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'DELETE')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'TRUNCATE')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'REFERENCES')
                   OR has_table_privilege(api_role, 'public.alembic_version', 'TRIGGER') THEN
                    RAISE EXCEPTION 'API role % retains effective alembic_version access', api_role;
                END IF;
                IF has_any_column_privilege(api_role, 'public.alembic_version', 'SELECT')
                   OR has_any_column_privilege(api_role, 'public.alembic_version', 'INSERT')
                   OR has_any_column_privilege(api_role, 'public.alembic_version', 'UPDATE')
                   OR has_any_column_privilege(api_role, 'public.alembic_version', 'REFERENCES') THEN
                    RAISE EXCEPTION 'API role % retains effective alembic_version column access', api_role;
                END IF;
                IF has_schema_privilege(api_role, 'finwise_migration_private', 'USAGE')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'SELECT')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'INSERT')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'UPDATE')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'DELETE')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'TRUNCATE')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'REFERENCES')
                   OR has_table_privilege(api_role, 'finwise_migration_private.alembic_version_acl_snapshot', 'TRIGGER') THEN
                    RAISE EXCEPTION 'API role % can access the private ACL snapshot', api_role;
                END IF;
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            alembic_owner text;
            database_owner text;
            public_owner text;
            acl_edge record;
            grantee_sql text;
            grant_option_sql text;
        BEGIN
            IF current_database() <> 'postgres' OR current_user <> 'postgres' THEN
                RAISE EXCEPTION
                    'ACL restoration requires the verified postgres database and postgres migration role';
            END IF;
            SELECT pg_catalog.pg_get_userbyid(datdba)
              INTO database_owner
              FROM pg_catalog.pg_database
             WHERE datname = current_database();
            SELECT pg_catalog.pg_get_userbyid(nspowner)
              INTO public_owner
              FROM pg_catalog.pg_namespace
             WHERE nspname = 'public';
            SELECT pg_catalog.pg_get_userbyid(relowner)
              INTO alembic_owner
              FROM pg_catalog.pg_class
             WHERE oid = to_regclass('public.alembic_version');
            IF database_owner <> current_user
               OR public_owner <> 'pg_database_owner'
               OR alembic_owner <> current_user THEN
                RAISE EXCEPTION 'ACL restoration target ownership differs from the reviewed state';
            END IF;
            IF EXISTS (
                SELECT 1
                  FROM finwise_migration_private.alembic_version_acl_snapshot
                 WHERE grantor <> current_user
                    OR (grantee <> 'PUBLIC' AND NOT EXISTS (
                        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = grantee
                    ))
            ) THEN
                RAISE EXCEPTION 'ACL snapshot grantor or grantee is not available for exact restoration';
            END IF;
            IF EXISTS (
                SELECT 1
                  FROM unnest(ARRAY['anon', 'authenticated', 'service_role']) AS api_roles(role_name)
                 WHERE has_table_privilege(role_name, 'public.alembic_version', 'SELECT')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'INSERT')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'UPDATE')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'DELETE')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'TRUNCATE')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'REFERENCES')
                    OR has_table_privilege(role_name, 'public.alembic_version', 'TRIGGER')
                    OR has_any_column_privilege(role_name, 'public.alembic_version', 'SELECT')
                    OR has_any_column_privilege(role_name, 'public.alembic_version', 'INSERT')
                    OR has_any_column_privilege(role_name, 'public.alembic_version', 'UPDATE')
                    OR has_any_column_privilege(role_name, 'public.alembic_version', 'REFERENCES')
            ) THEN
                RAISE EXCEPTION
                    'API-role access changed after the ACL correction; refusing to merge grants during downgrade';
            END IF;
            FOR acl_edge IN
                SELECT grantee, grantor, privilege_type, is_grantable
                       , object_kind, column_name
                  FROM finwise_migration_private.alembic_version_acl_snapshot
                 ORDER BY object_kind, grantee, privilege_type
            LOOP
                IF acl_edge.grantor <> current_user THEN
                    RAISE EXCEPTION
                        'cannot restore alembic_version ACL edge: grantor differs from current role';
                END IF;
                IF acl_edge.privilege_type NOT IN
                   ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER') THEN
                    RAISE EXCEPTION 'unexpected alembic_version ACL privilege in snapshot';
                END IF;
                IF acl_edge.object_kind NOT IN ('TABLE', 'COLUMN') THEN
                    RAISE EXCEPTION 'unexpected alembic_version ACL object in snapshot';
                END IF;
                IF acl_edge.grantee = 'PUBLIC' THEN
                    grantee_sql := 'PUBLIC';
                ELSE
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = acl_edge.grantee
                    ) THEN
                        RAISE EXCEPTION 'cannot restore ACL: grantee role is absent';
                    END IF;
                    grantee_sql := format('%I', acl_edge.grantee);
                END IF;
                grant_option_sql := CASE
                    WHEN acl_edge.is_grantable THEN ' WITH GRANT OPTION'
                    ELSE ''
                END;
                IF acl_edge.object_kind = 'TABLE' THEN
                    EXECUTE format(
                        'GRANT %s ON TABLE public.alembic_version TO %s%s',
                        acl_edge.privilege_type,
                        grantee_sql,
                        grant_option_sql
                    );
                ELSE
                    IF acl_edge.privilege_type NOT IN ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES') THEN
                        RAISE EXCEPTION 'unexpected column privilege in ACL snapshot';
                    END IF;
                    EXECUTE format(
                        'GRANT %s (%I) ON TABLE public.alembic_version TO %s%s',
                        acl_edge.privilege_type,
                        acl_edge.column_name,
                        grantee_sql,
                        grant_option_sql
                    );
                END IF;
            END LOOP;
        END
        $$;
        """
    )
    op.drop_table("alembic_version_acl_snapshot", schema="finwise_migration_private")
    op.execute("DROP SCHEMA finwise_migration_private")
