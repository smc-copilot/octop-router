-- TEMPLATE ONLY. Replace every IP and database name before execution.
-- Run in database octop-ldap after 001_init.sql.
-- One enabled primary database relationship is registered for each app.

BEGIN;

WITH dbs AS (
    INSERT INTO public.octop_databases
        (db_code, database_name, db_host, db_port, status)
    VALUES
        ('octop-bc01-db', 'REPLACE_OCTOP01_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc02-db', 'REPLACE_OCTOP02_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc03-db', 'REPLACE_OCTOP03_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc04-db', 'REPLACE_OCTOP04_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc05-db', 'REPLACE_OCTOP05_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc06-db', 'REPLACE_OCTOP06_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc07-db', 'REPLACE_OCTOP07_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc08-db', 'REPLACE_OCTOP08_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc09-db', 'REPLACE_OCTOP09_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled'),
        ('octop-bc10-db', 'REPLACE_OCTOP10_DATABASE', 'REPLACE_POSTGRES_HOST', 5432, 'enabled')
    ON CONFLICT (db_code) DO UPDATE SET
        database_name = EXCLUDED.database_name,
        db_host = EXCLUDED.db_host,
        db_port = EXCLUDED.db_port,
        status = EXCLUDED.status,
        updated_at = NOW()
    RETURNING id, db_code
), apps AS (
    INSERT INTO public.octop_applications
        (app_code, app_name, center_code, public_url, nginx_port, upstream_host, upstream_port, status)
    VALUES
        ('octop-bc01', 'Octop 业务中心 01', 'bc01', 'https://ai.superice.com:8091/', 8091, 'REPLACE_OCTOP01_IP', 8088, 'enabled'),
        ('octop-bc02', 'Octop 业务中心 02', 'bc02', 'https://ai.superice.com:8092/', 8092, 'REPLACE_OCTOP02_IP', 8088, 'enabled'),
        ('octop-bc03', 'Octop 业务中心 03', 'bc03', 'https://ai.superice.com:8093/', 8093, 'REPLACE_OCTOP03_IP', 8088, 'enabled'),
        ('octop-bc04', 'Octop 业务中心 04', 'bc04', 'https://ai.superice.com:8094/', 8094, 'REPLACE_OCTOP04_IP', 8088, 'enabled'),
        ('octop-bc05', 'Octop 业务中心 05', 'bc05', 'https://ai.superice.com:8095/', 8095, 'REPLACE_OCTOP05_IP', 8088, 'enabled'),
        ('octop-bc06', 'Octop 业务中心 06', 'bc06', 'https://ai.superice.com:8096/', 8096, 'REPLACE_OCTOP06_IP', 8088, 'enabled'),
        ('octop-bc07', 'Octop 业务中心 07', 'bc07', 'https://ai.superice.com:8097/', 8097, 'REPLACE_OCTOP07_IP', 8088, 'enabled'),
        ('octop-bc08', 'Octop 业务中心 08', 'bc08', 'https://ai.superice.com:8098/', 8098, 'REPLACE_OCTOP08_IP', 8088, 'enabled'),
        ('octop-bc09', 'Octop 业务中心 09', 'bc09', 'https://ai.superice.com:8099/', 8099, 'REPLACE_OCTOP09_IP', 8088, 'enabled'),
        ('octop-bc10', 'Octop 业务中心 10', 'bc10', 'https://ai.superice.com:8100/', 8100, 'REPLACE_OCTOP10_IP', 8088, 'enabled')
    ON CONFLICT (app_code) DO UPDATE SET
        app_name = EXCLUDED.app_name,
        center_code = EXCLUDED.center_code,
        public_url = EXCLUDED.public_url,
        nginx_port = EXCLUDED.nginx_port,
        upstream_host = EXCLUDED.upstream_host,
        upstream_port = EXCLUDED.upstream_port,
        status = EXCLUDED.status,
        updated_at = NOW()
    RETURNING id, app_code
)
INSERT INTO public.octop_application_databases
    (application_id, database_id, relation_type, is_primary, status)
SELECT a.id, d.id, 'primary', TRUE, 'enabled'
FROM apps a
JOIN dbs d ON d.db_code = a.app_code || '-db'
ON CONFLICT (application_id, database_id, relation_type)
DO UPDATE SET is_primary = TRUE, status = 'enabled';

COMMIT;
