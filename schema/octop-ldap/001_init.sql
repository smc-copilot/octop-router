-- Run this migration once against the dedicated octop-ldap database.
-- The Router receives a read-only DB role; never grant it DDL privileges.

CREATE TABLE IF NOT EXISTS public.octop_applications (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    app_code            VARCHAR(64) NOT NULL UNIQUE,
    app_name            VARCHAR(160) NOT NULL,
    center_code         VARCHAR(64) NOT NULL,
    public_url          TEXT NOT NULL,
    nginx_port          INTEGER NOT NULL UNIQUE,
    upstream_host       VARCHAR(255) NOT NULL,
    upstream_port       INTEGER NOT NULL,
    status              VARCHAR(16) NOT NULL DEFAULT 'enabled'
                        CHECK (status IN ('enabled', 'disabled')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (nginx_port BETWEEN 1 AND 65535),
    CHECK (upstream_port BETWEEN 1 AND 65535)
);

CREATE TABLE IF NOT EXISTS public.octop_databases (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    db_code             VARCHAR(64) NOT NULL UNIQUE,
    database_name       VARCHAR(63) NOT NULL UNIQUE,
    db_type             VARCHAR(32) NOT NULL DEFAULT 'postgresql'
                        CHECK (db_type IN ('postgresql')),
    db_host             VARCHAR(255) NOT NULL,
    db_port             INTEGER NOT NULL DEFAULT 5432,
    secret_ref          VARCHAR(255),
    status              VARCHAR(16) NOT NULL DEFAULT 'enabled'
                        CHECK (status IN ('enabled', 'disabled')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (db_port BETWEEN 1 AND 65535)
);

CREATE TABLE IF NOT EXISTS public.octop_application_databases (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id      BIGINT NOT NULL REFERENCES public.octop_applications(id) ON DELETE RESTRICT,
    database_id         BIGINT NOT NULL REFERENCES public.octop_databases(id) ON DELETE RESTRICT,
    relation_type       VARCHAR(32) NOT NULL DEFAULT 'primary'
                        CHECK (relation_type IN ('primary', 'memory', 'audit', 'other')),
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    status              VARCHAR(16) NOT NULL DEFAULT 'enabled'
                        CHECK (status IN ('enabled', 'disabled')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (application_id, database_id, relation_type),
    CHECK ((relation_type = 'primary' AND is_primary IS TRUE)
        OR (relation_type <> 'primary' AND is_primary IS FALSE))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_octop_application_primary_db
    ON public.octop_application_databases(application_id)
    WHERE relation_type = 'primary' AND is_primary IS TRUE AND status = 'enabled';

CREATE INDEX IF NOT EXISTS ix_octop_application_databases_database
    ON public.octop_application_databases(database_id);

COMMENT ON TABLE public.octop_applications IS 'Registry of independently deployed Octop application instances';
COMMENT ON TABLE public.octop_databases IS 'Metadata of independent Octop databases on PostgreSQL services; no passwords stored here';
COMMENT ON TABLE public.octop_application_databases IS 'Relationship between Octop application instances and their database(s)';
COMMENT ON COLUMN public.octop_databases.secret_ref IS 'Optional external secret reference; never store plaintext DB passwords';
