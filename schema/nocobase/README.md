# NocoBase DB contract (already provisioned)

Router v2.2 assumes the user-assignment table and view have already been created in database `nocobase3`.
It does not create or modify NocoBase tables at startup.

The Router reads exactly this view contract:

```sql
SELECT employee_no, app_code, is_default
FROM public.v_octop_user_routes
WHERE employee_no = $1
  AND is_active IS TRUE;
```

Required view columns:

- `employee_no text`: lowercase NocoBase `public."user".username`; preserve leading zeroes.
- `app_code text`: matches `octop-ldap.public.octop_applications.app_code`.
- `is_default boolean`: default app for multi-app employees.
- `is_active boolean`: excludes service, disabled, deleted, disabled assignment and out-of-date assignment.

The underlying NocoBase user collection is `public."user"` (singular, quoted). The Router does not query it directly and does not read passwords or password hashes.

## Verify existing view

Run in `nocobase3`:

```sql
SELECT employee_no, app_code, is_default, is_active
FROM public.v_octop_user_routes
ORDER BY employee_no, is_default DESC;
```

For a test employee:

```sql
SELECT employee_no, app_code, is_default, is_active
FROM public.v_octop_user_routes
WHERE employee_no = lower('10001');
```

Do not rerun any NocoBase DDL if the collection and view are already prepared. If your physical assignment table differs, that does not affect Router as long as this view contract is satisfied.
