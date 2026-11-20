-- Run once in the dedicated octop-ldap database as owner/admin.
-- Replace password first. Do not grant access to any Octop operational database.
CREATE ROLE octop_router_ldap_ro LOGIN PASSWORD 'REPLACE_WITH_STRONG_SECRET';
GRANT CONNECT ON DATABASE "octop-ldap" TO octop_router_ldap_ro;
GRANT USAGE ON SCHEMA public TO octop_router_ldap_ro;
GRANT SELECT ON public.octop_applications TO octop_router_ldap_ro;
GRANT SELECT ON public.octop_databases TO octop_router_ldap_ro;
GRANT SELECT ON public.octop_application_databases TO octop_router_ldap_ro;
