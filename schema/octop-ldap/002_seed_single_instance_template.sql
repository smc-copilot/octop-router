-- POC seed for Octop 01 only. Replace example IP and database name.
-- Run in database octop-ldap after 001_init.sql.
BEGIN;

INSERT INTO public.octop_databases
    (db_code, database_name, db_host, db_port, status)
VALUES
    ('octop-bc01-db', 'REPLACE_WITH_OCTOP01_DATABASE', 'REPLACE_WITH_POSTGRES_HOST', 5432, 'enabled')
ON CONFLICT (db_code) DO UPDATE SET
    database_name = EXCLUDED.database_name,
    db_host = EXCLUDED.db_host,
    db_port = EXCLUDED.db_port,
    status = EXCLUDED.status,
    updated_at = NOW();

INSERT INTO public.octop_applications
    (app_code, app_name, center_code, public_url, nginx_port, upstream_host, upstream_port, status)
VALUES
    ('octop-bc01', 'Octop 业务中心 01', 'bc01',
     'https://ai.superice.com:8091/', 8091,
     'REPLACE_WITH_OCTOP01_INTERNAL_IP', 8088, 'enabled')
ON CONFLICT (app_code) DO UPDATE SET
    app_name = EXCLUDED.app_name,
    center_code = EXCLUDED.center_code,
    public_url = EXCLUDED.public_url,
    nginx_port = EXCLUDED.nginx_port,
    upstream_host = EXCLUDED.upstream_host,
    upstream_port = EXCLUDED.upstream_port,
    status = EXCLUDED.status,
    updated_at = NOW();

INSERT INTO public.octop_application_databases
    (application_id, database_id, relation_type, is_primary, status)
SELECT a.id, d.id, 'primary', TRUE, 'enabled'
FROM public.octop_applications a
JOIN public.octop_databases d ON d.db_code = 'octop-bc01-db'
WHERE a.app_code = 'octop-bc01'
ON CONFLICT (application_id, database_id, relation_type)
DO UPDATE SET is_primary = TRUE, status = 'enabled';

COMMIT;
