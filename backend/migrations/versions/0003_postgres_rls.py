"""Restrict database access to the trusted FastAPI role and apply RLS.

The migration creates a non-login group role. A deployment administrator must
grant that role to a dedicated, non-owner, non-superuser login used by FastAPI.
"""
from alembic import op

revision = "0003_postgres_rls"
down_revision = "0002_user_ownership"
branch_labels = None
depends_on = None


TABLES = (
    "user_identities",
    "investor_profiles",
    "portfolio_holdings",
    "analysis_sessions",
    "signal_evaluations",
    "financial_documents",
    "document_chunks",
)


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'finwise_backend') THEN
                CREATE ROLE finwise_backend NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            ELSE
                ALTER ROLE finwise_backend NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO finwise_backend")
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

    table_list = ", ".join(TABLES)
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {table_list} FROM PUBLIC")
    op.execute(
        "GRANT SELECT, INSERT ON TABLE user_identities, investor_profiles, "
        "portfolio_holdings, analysis_sessions TO finwise_backend"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE signal_evaluations, "
        "financial_documents TO finwise_backend"
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE document_chunks TO finwise_backend"
    )

    # Supabase PostgREST roles receive no table privileges on application data.
    # Revoking service_role too avoids treating its RLS bypass attribute as an
    # acceptable application access path. Policies still protect other SQL roles.
    op.execute(
        """
        DO $$
        DECLARE
            api_role text;
            table_name text;
            privilege_name text;
        BEGIN
            FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
                    EXECUTE format('REVOKE CREATE ON SCHEMA public FROM %I', api_role);
                    EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %s FROM %I',
                        'user_identities, investor_profiles, portfolio_holdings, analysis_sessions, signal_evaluations, financial_documents, document_chunks',
                        api_role);
                    EXECUTE format('REVOKE finwise_backend FROM %I', api_role);

                    -- Direct REVOKE statements do not remove privileges or
                    -- memberships inherited through another role. Fail the
                    -- migration instead of leaving a Data API role with an
                    -- indirect path to application data (notably service_role,
                    -- which may bypass RLS).
                    IF pg_has_role(api_role, 'finwise_backend', 'MEMBER') THEN
                        RAISE EXCEPTION 'Supabase API role % inherits finwise_backend membership', api_role;
                    END IF;

                    -- Check effective privilege, not only direct ACL entries:
                    -- an API role must not retain CREATE through another role.
                    IF has_schema_privilege(api_role, 'public', 'CREATE') THEN
                        RAISE EXCEPTION
                            'Supabase API role % retains effective CREATE on schema public',
                            api_role;
                    END IF;

                    FOREACH table_name IN ARRAY ARRAY[
                        'user_identities', 'investor_profiles', 'portfolio_holdings',
                        'analysis_sessions', 'signal_evaluations',
                        'financial_documents', 'document_chunks'
                    ] LOOP
                        FOREACH privilege_name IN ARRAY ARRAY[
                            'SELECT', 'INSERT', 'UPDATE', 'DELETE',
                            'TRUNCATE', 'REFERENCES', 'TRIGGER'
                        ] LOOP
                            IF has_table_privilege(
                                api_role,
                                format('public.%I', table_name),
                                privilege_name
                            ) THEN
                                RAISE EXCEPTION
                                    'Supabase API role % retains inherited % privilege on public.%',
                                    api_role, privilege_name, table_name;
                            END IF;
                        END LOOP;

                        FOREACH privilege_name IN ARRAY ARRAY[
                            'SELECT', 'INSERT', 'UPDATE', 'REFERENCES'
                        ] LOOP
                            IF has_any_column_privilege(
                                api_role,
                                format('public.%I', table_name),
                                privilege_name
                            ) THEN
                                RAISE EXCEPTION
                                    'Supabase API role % retains inherited % column privilege on public.%',
                                    api_role, privilege_name, table_name;
                            END IF;
                        END LOOP;
                    END LOOP;
                END IF;
            END LOOP;
        END
        $$;
        """
    )
    # Future tables created by the migration role fail closed unless a later
    # migration explicitly grants access and defines its RLS policies.
    op.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM PUBLIC")
    op.execute(
        """
        DO $$
        DECLARE api_role text;
        BEGIN
            FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated', 'service_role'] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
                    EXECUTE format(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I',
                        api_role);
                END IF;
            END LOOP;
        END
        $$;
        """
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY finwise_identity_access ON user_identities
        FOR ALL TO finwise_backend
        USING (
            current_setting('app.is_operator', true) = 'true'
            OR (issuer = current_setting('app.supabase_issuer', true)
                AND subject = current_setting('app.supabase_subject', true))
        )
        WITH CHECK (
            current_setting('app.is_operator', true) = 'true'
            OR (issuer = current_setting('app.supabase_issuer', true)
                AND subject = current_setting('app.supabase_subject', true))
        )
        """
    )
    op.execute(
        """
        CREATE POLICY finwise_profile_access ON investor_profiles
        FOR ALL TO finwise_backend
        USING (
            current_setting('app.is_operator', true) = 'true'
            OR owner_id = current_setting('app.user_identity_id', true)
            OR is_demo IS TRUE
        )
        WITH CHECK (
            current_setting('app.is_operator', true) = 'true'
            OR (owner_id = current_setting('app.user_identity_id', true) AND is_demo IS FALSE)
        )
        """
    )
    op.execute(
        """
        CREATE POLICY finwise_holding_access ON portfolio_holdings
        FOR ALL TO finwise_backend
        USING (
            current_setting('app.is_operator', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM investor_profiles p
                WHERE p.id = profile_id
                  AND (p.owner_id = current_setting('app.user_identity_id', true)
                       OR p.is_demo IS TRUE)
            )
        )
        WITH CHECK (
            current_setting('app.is_operator', true) = 'true'
            OR EXISTS (
                SELECT 1 FROM investor_profiles p
                WHERE p.id = profile_id
                  AND p.owner_id = current_setting('app.user_identity_id', true)
                  AND p.is_demo IS FALSE
            )
        )
        """
    )

    for table in ("analysis_sessions", "signal_evaluations"):
        op.execute(
            f"""
            CREATE POLICY finwise_{table}_access ON {table}
            FOR ALL TO finwise_backend
            USING (
                current_setting('app.is_operator', true) = 'true'
                OR owner_id = current_setting('app.user_identity_id', true)
            )
            WITH CHECK (
                current_setting('app.is_operator', true) = 'true'
                OR owner_id = current_setting('app.user_identity_id', true)
            )
            """
        )

    for table in ("financial_documents", "document_chunks"):
        op.execute(
            f"""
            CREATE POLICY finwise_{table}_read ON {table}
            FOR SELECT TO finwise_backend USING (true)
            """
        )
        op.execute(
            f"""
            CREATE POLICY finwise_{table}_operator_write ON {table}
            FOR ALL TO finwise_backend
            USING (current_setting('app.is_operator', true) = 'true')
            WITH CHECK (current_setting('app.is_operator', true) = 'true')
            """
        )


def downgrade() -> None:
    # Leave FORCE RLS enabled with no policies, which denies access by default.
    # Restoring unrestricted table access during downgrade would be unsafe.
    for table, policies in {
        "user_identities": ("finwise_identity_access",),
        "investor_profiles": ("finwise_profile_access",),
        "portfolio_holdings": ("finwise_holding_access",),
        "analysis_sessions": ("finwise_analysis_sessions_access",),
        "signal_evaluations": ("finwise_signal_evaluations_access",),
        "financial_documents": (
            "finwise_financial_documents_read", "finwise_financial_documents_operator_write"
        ),
        "document_chunks": (
            "finwise_document_chunks_read", "finwise_document_chunks_operator_write"
        ),
    }.items():
        for policy in policies:
            op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
    op.execute(f"REVOKE ALL PRIVILEGES ON TABLE {', '.join(TABLES)} FROM finwise_backend")
