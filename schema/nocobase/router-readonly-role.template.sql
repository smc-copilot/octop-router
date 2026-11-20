-- Run once in nocobase3 as database owner/admin. Replace password first.
-- If the role already exists, skip CREATE ROLE and rotate its password separately.
CREATE ROLE octop_router_nocobase_ro LOGIN PASSWORD 'REPLACE_WITH_STRONG_SECRET';
GRANT CONNECT ON DATABASE nocobase3 TO octop_router_nocobase_ro;
GRANT USAGE ON SCHEMA public TO octop_router_nocobase_ro;
GRANT SELECT ON public.v_octop_user_routes TO octop_router_nocobase_ro;

-- Verify as the Router role:
-- SET ROLE octop_router_nocobase_ro;
-- SELECT employee_no, app_code, is_default FROM public.v_octop_user_routes
--  WHERE employee_no = '10001' AND is_active IS TRUE;
-- RESET ROLE;
