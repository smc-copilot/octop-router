-- Run in nocobase3. Read-only verification; does not modify NocoBase.
SELECT employee_no, app_code, is_default, is_active
FROM public.v_octop_user_routes
WHERE employee_no = lower('10001')
ORDER BY is_default DESC, app_code;
