from __future__ import annotations
import argparse, getpass, sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from postgres_role_inspection import (
    format_api_role_findings,
    format_runtime_role_finding,
    inspect_api_roles,
    inspect_runtime_role,
)
HOST='aws-0-ap-south-1.pooler.supabase.com'; PORT=5432; DB='postgres'
LOGIN='postgres.davqezmxaqkxdijkafhj'; PROJECT='davqezmxaqkxdijkafhj'
APP_TABLES={'user_identities','investor_profiles','portfolio_holdings','analysis_sessions','signal_evaluations','financial_documents','document_chunks'}
parser=argparse.ArgumentParser(description="Read-only Supabase PostgreSQL identity/schema preflight")
parser.add_argument("--ssl-root-cert", required=True, help="Path to this project's database CA certificate downloaded from Supabase Dashboard")
args=parser.parse_args()
ca_path=Path(args.ssl_root_cert).expanduser()
if not ca_path.is_file():
    print("Preflight stopped: the specified Supabase CA certificate file does not exist.", file=sys.stderr)
    raise SystemExit(2)
pw=getpass.getpass('Disposable Supabase database password (hidden): ')
if not pw: print('Stopped: password not entered.',file=sys.stderr); raise SystemExit(2)
url=URL.create('postgresql+psycopg',username=LOGIN,password=pw,host=HOST,port=PORT,database=DB,query={'sslmode':'verify-full','sslrootcert':str(ca_path.resolve()),'connect_timeout':'10'})
try:
    engine=create_engine(url,pool_pre_ping=True,hide_parameters=True)
    with engine.connect() as c:
      with c.begin():
        c.exec_driver_sql('SET TRANSACTION READ ONLY')
        ident=c.execute(text('SELECT current_database() db,current_user current_role,session_user login_role,version() server_version,inet_server_addr()::text server_address,inet_server_port() server_port')).mappings().one()
        role=c.execute(text("SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolcanlogin,has_database_privilege(current_user,current_database(),'CONNECT') db_connect FROM pg_catalog.pg_roles WHERE rolname=current_user")).mappings().one_or_none()
        db_owner=c.execute(text("SELECT pg_catalog.pg_get_userbyid(datdba) owner,current_user=pg_catalog.pg_get_userbyid(datdba) is_current_role_owner,pg_has_role(current_user,'pg_database_owner','MEMBER') is_database_owner_member,pg_has_role(current_user,'pg_database_owner','USAGE') has_database_owner_privileges FROM pg_catalog.pg_database WHERE datname=current_database()")).mappings().one_or_none()
        schema=c.execute(text("SELECT pg_catalog.pg_get_userbyid(n.nspowner) owner,pg_has_role(current_user,n.nspowner,'MEMBER') owner_role_member,pg_has_role(current_user,n.nspowner,'USAGE') owner_role_privileges,has_schema_privilege(current_user,'public','USAGE') usage,has_schema_privilege(current_user,'public','CREATE') create_priv FROM pg_catalog.pg_namespace n WHERE n.nspname='public'")).mappings().one_or_none()
        rels=list(c.execute(text("SELECT c.relname,c.relkind FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname")).mappings().all())
        backend=c.execute(text("SELECT rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolcanlogin FROM pg_catalog.pg_roles WHERE rolname='finwise_backend'")).mappings().one_or_none()
        api_roles=inspect_api_roles(c)
        runtime_role=inspect_runtime_role(c)
        hist=c.execute(text("SELECT pg_catalog.to_regclass('public.alembic_version') IS NOT NULL")).scalar_one()
        versions=[r[0] for r in c.execute(text('SELECT version_num FROM public.alembic_version ORDER BY version_num')).all()] if hist else []
    for key in ('db','current_role','login_role','server_version','server_address','server_port'): print(f'{key}={ident[key]}')
    print('configured_host_matches_expected=true'); print('configured_project_ref_matches_login=true')
    print(f'migration_role_attributes={dict(role) if role else None}')
    print(f'database_owner_check={dict(db_owner) if db_owner else None}')
    print(f'public_schema_privileges={dict(schema) if schema else None}')
    print(f'public_relations={[(x["relname"],x["relkind"]) for x in rels]}')
    print(f'alembic_version_table_exists={hist}'); print(f'alembic_versions={versions}')
    print(f'finwise_backend_role_exists={backend is not None}')
    if backend: print(f'finwise_backend_attributes={dict(backend)}')
    print(format_runtime_role_finding(runtime_role))
    for finding in format_api_role_findings(api_roles): print(finding)
    present=APP_TABLES.intersection(x['relname'] for x in rels)
    capable=bool(role and schema and role['rolcreaterole'] and role['db_connect'] and schema['usage'] and schema['create_priv'] and (schema['owner']==ident['current_role'] or schema['owner_role_privileges'] or role['rolsuper']))
    target_ok=ident['db']==DB and ident['current_role']=='postgres' and ident['login_role']=='postgres'
    api_roles_clear = all(
        finding is None or finding["public_create"] is False
        for finding in api_roles.values()
    )
    print(f'api_roles_effective_public_create_absent={api_roles_clear}')
    safe=target_ok and not present and not hist and capable and backend is None and runtime_role is None and api_roles_clear
    print(f'expected_application_tables_present={sorted(present)}'); print(f'application_tables_absent={not present}')
    print(f'migration_history_absent={not hist}'); print(f'migration_capabilities_sufficient_for_0001_0003={capable}')
    print(f'server_identity_matches_expected_target={target_ok}'); print(f'safe_to_consider_next_migration_step={safe}')
    engine.dispose(); raise SystemExit(0 if safe else 3)
except SystemExit: raise
except Exception as exc:
    print(
        f'Preflight failed: {type(exc).__name__}; details redacted.',
        file=sys.stderr,
    )
    raise SystemExit(1)
finally: pw=''
