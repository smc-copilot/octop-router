# Octop LDAP Router v2.2

NocoBase + `octop-ldap` PostgreSQL-backed employee-to-Octop routing service.

**This is a router, not an authenticator or SSO service.** It looks up the employee number in the already-prepared NocoBase view, resolves the authorized Octop instance from `octop-ldap`, and redirects the browser. The target Octop continues to authenticate the employee against its own configured AD/LDAP directory and issues its own JWT.

## 1. Confirmed environment and assumptions

- NocoBase database: `nocobase3`.
- NocoBase built-in user collection: `public."user"` (singular, quoted); username is lowercase; leading zeroes are significant; service, disabled and deleted users are excluded by the view.
- NocoBase assignment table and `public.v_octop_user_routes` have already been created by the operator. **This package does not recreate or alter them.**
- Router reads only `public.v_octop_user_routes` with columns `employee_no`, `app_code`, `is_default`, `is_active`.
- Octop registry database: `octop-ldap`.
- Registry tables: `public.octop_applications`, `public.octop_databases`, `public.octop_application_databases`.
- Ten Octop instances remain independently deployed, with independent operational databases and native AD/LDAP authentication.
- Example public URL/ports: `https://ai.superice.com:8091/` through `:8100/`. Replace the upstream private IPs with the actual server addresses.

## 2. Request flow

1. Employee opens `https://ai.superice.com:8090/`.
2. Employee enters the company employee number (username). Router lowercases it for lookup; it does not trim whitespace, strip domain prefixes, strip UPN suffixes, or remove leading zeroes.
3. Router queries `nocobase3.public.v_octop_user_routes` and gets active application assignments.
4. If one active assignment exists, it is selected. If multiple assignments exist, exactly one must have `is_default=true`.
5. Router queries `octop-ldap` and checks that the selected app is enabled, its URL is allowlisted, its registered Nginx port matches the URL port, and it has exactly one enabled primary database relation.
6. Browser is redirected to the selected Octop URL.
7. Employee enters the company AD/LDAP password on that Octop login page. Octop authenticates and issues its own JWT.

The browser remembers only the employee number in localStorage to simplify repeat routing. It never stores a password, LDAP credential, Octop JWT, or database credential. Use “切换账号 / 清除本机记忆” on shared workstations.

## 3. Package layout

```text
octop-ldap-router-v2.2/
├── router/
│   ├── app.py                         # FastAPI endpoints and input validation
│   ├── repository.py                  # read-only NocoBase + octop-ldap queries
│   └── index.html                     # employee entry page
├── schema/
│   ├── nocobase/
│   │   ├── README.md                  # existing view contract and verification
│   │   ├── verify.sql                 # read-only test query
│   │   └── router-readonly-role.template.sql
│   └── octop-ldap/
│       ├── 001_init.sql               # app/database registry tables
│       ├── 002_seed_single_instance_template.sql # Octop 01 POC seed
│       ├── seed_ten_centers_template.sql          # full ten-center seed
│       └── 003_router_readonly_role.template.sql
├── nginx/
│   ├── 8090-location-snippet.conf     # merge into existing 8090 server
│   └── octop-centers.conf             # 8091-8100 reverse proxy template
├── tests/test_routes.py
├── scripts/check-dependencies.sh
├── .env.example
├── compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 4. Deploy Router on the independent Nginx server

The container binds only to `127.0.0.1:9080` on the Nginx host. Public access is through the existing Nginx `:8090` server.

```bash
unzip octop-ldap-router-v2.2.zip
cd octop-ldap-router-v2.2
cp .env.example .env
```

Edit `.env`:

```ini
NOCOBASE_DATABASE_URL=postgresql://octop_router_nocobase_ro:URL_ENCODED_PASSWORD@POSTGRES_HOST:5432/nocobase3?sslmode=verify-full
OCTOP_LDAP_DATABASE_URL=postgresql://octop_router_ldap_ro:URL_ENCODED_PASSWORD@POSTGRES_HOST:5432/octop-ldap?sslmode=verify-full
PGCONNECT_TIMEOUT=5
OCTOP_EXTERNAL_HOST=ai.superice.com
OCTOP_ALLOWED_PORTS=8091,8092,8093,8094,8095,8096,8097,8098,8099,8100
OCTOP_EMPLOYEE_NO_REGEX=^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$
```

Use URL-encoded passwords in DSNs. If your PostgreSQL server uses a private CA, install the CA certificate into the container and configure `sslrootcert`/`sslmode` accordingly. Do not change to `sslmode=disable` for production merely to bypass certificate errors.

The two DSNs may point to the same PostgreSQL host and port, but their database names and read-only roles are different. PostgreSQL databases cannot be joined with an ordinary cross-database SQL JOIN; Router opens two independent connections.

Start:

```bash
./scripts/check-dependencies.sh
docker compose up -d --build
docker compose ps
docker compose logs -f octop-router
```

Local health check:

```bash
curl http://127.0.0.1:9080/healthz
```

Expected shape:

```json
{"status":"ok","version":"2.2.0","checks":{"nocobase":"ok","octop_ldap":"ok"}}
```

## 5. Nginx integration

### 5.1 Existing port 8090

Merge `nginx/8090-location-snippet.conf` into the existing `server` block for `ai.superice.com:8090`. Do not create a duplicate `listen 8090` block. This sends the unified entry page and `/api/resolve` to Router at `127.0.0.1:9080`.

### 5.2 Octop instance ports

The supplied `nginx/octop-centers.conf` is a template for ports 8091-8100. Replace:

- `10.20.1.21` ... `10.20.1.30` with the actual private Octop server IPs.
- TLS certificate paths with the real certificate paths.
- `8088` if any Octop listens on another internal port.

Include the `map` directives in the Nginx `http {}` context. Add the `server` block in the same context.

**Important network prerequisite:** redirect targets are `https://ai.superice.com:8091/` through `:8100/`. Those external ports must be routed through the firewall/NAT to this Nginx server and allowed by host firewall. If only external port 8090 is open, the browser cannot reach the redirected Octop port; this port-based version will not work until the additional ports are opened. In that case a different single-port routing design is required.

Validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Test each upstream from the Nginx host before browser testing:

```bash
curl http://OCTOP01_PRIVATE_IP:8088/api/health
curl http://OCTOP02_PRIVATE_IP:8088/api/health
```

Test through Nginx after enabling TLS and port forwarding:

```bash
curl -i https://ai.superice.com:8091/api/health
curl -i https://ai.superice.com:8092/api/health
```

## 6. Database setup and verification

### 6.1 NocoBase (already prepared)

Do not rerun NocoBase table/view creation. Verify the view:

```sql
SELECT employee_no, app_code, is_default, is_active
FROM public.v_octop_user_routes
WHERE employee_no = lower('10001')
ORDER BY is_default DESC, app_code;
```

The Router requires a read-only role that can `CONNECT` to `nocobase3`, `USAGE` on schema `public`, and `SELECT` on `public.v_octop_user_routes` only. See `schema/nocobase/router-readonly-role.template.sql` if this role has not yet been created.

### 6.2 octop-ldap

If registry tables are not yet created, run `schema/octop-ldap/001_init.sql` in the `octop-ldap` database. For the first POC, edit and run `002_seed_single_instance_template.sql` after replacing the Octop 01 private IP, actual database name, and PostgreSQL host. When all ten instances are ready, use `seed_ten_centers_template.sql` after replacing all ten database names and private IPs.

Create the read-only role using `003_router_readonly_role.template.sql` if it does not already exist. The Router role must not be granted `CONNECT` to the ten Octop operational databases.

Verify Octop 01 registry:

```sql
SELECT a.app_code, a.public_url, a.nginx_port, a.upstream_host, a.upstream_port,
       d.database_name, ad.relation_type, ad.is_primary, ad.status AS relation_status
FROM public.octop_applications a
JOIN public.octop_application_databases ad ON ad.application_id = a.id
JOIN public.octop_databases d ON d.id = ad.database_id
WHERE a.app_code = 'octop-bc01';
```

For an enabled app, Router expects exactly one enabled primary DB relation, with `relation_type='primary'`, `is_primary=true`, `status='enabled'`, and the referenced database also `status='enabled'`.

## 7. POC test sequence (one employee, Octop 01)

1. In NocoBase, create the test employee through the normal NocoBase user flow. The employee must already exist in `public."user"` with `kind='person'`, `disabled_at IS NULL`, and `deleted_at IS NULL`.
2. Insert/enable one row in the existing user-to-Octop assignment collection for this user's `user_id`, with `app_code='octop-bc01'`, `is_default=true`, `enabled=true`, and current validity range.
3. Confirm the NocoBase view returns one active row for the employee number.
4. Confirm the `octop-ldap` app and primary DB relation are correct.
5. Check Router health.
6. Open `https://ai.superice.com:8090/`, enter the employee number, and submit.
7. Confirm browser redirects to `https://ai.superice.com:8091/`.
8. On Octop 01 login page, enter the company AD/LDAP username and password. The LDAP login attribute must match the username format entered here (for example employee number / `sAMAccountName`, according to your Octop LDAP config).
9. Confirm Octop login succeeds and `/api/auth/me` returns the expected Octop user.

Router lookup API:

```bash
curl -X POST https://ai.superice.com:8090/api/resolve \
  -H 'Content-Type: application/json' \
  -d '{"employee_id":"10001"}'
```

Expected response:

```json
{"target":"https://ai.superice.com:8091/","app_code":"octop-bc01"}
```

## 8. Routing rules and error codes

- One active assignment: route to it, even if `is_default=false`.
- Multiple active assignments: exactly one must have `is_default=true`.
- No active assignment: HTTP 404.
- Multiple defaults, no default for multiple apps, disabled/missing app, URL mismatch, or invalid primary DB relation: HTTP 409.
- Invalid employee number, domain prefix, or whitespace: HTTP 400.
- Either PostgreSQL database unavailable or DSN missing: HTTP 503.

## 9. Security boundaries and production checklist

- Router never receives employee password or LDAP password.
- Router never queries NocoBase password fields or hashes.
- Router never signs or receives Octop JWTs.
- Router database connections enforce read-only transactions and 5-second statement timeout.
- Use two distinct least-privilege PostgreSQL roles. The NocoBase role can select only the view; the registry role can select only the three registry tables.
- Never grant Router access to Octop operational databases or store DB passwords in `octop-ldap`.
- The employee number is a routing key, not proof of identity. The target Octop still authenticates against AD/LDAP.
- If all ten Octop instances accept every valid AD user, a user can manually browse to another center's port and authenticate there. Before production, add and test center-specific login admission on each Octop (e.g. an AD security-group/member allowlist in the LDAP login path). `admin_groups` must not be assumed to implement center membership.
- Browser cookies are not isolated by port, although localStorage is origin/port isolated. Test for cookie-name collisions between Octop instances; avoid shared cookie names for auth state.
- Router currently remembers employee number in browser localStorage only. Shared workstations should use the account-switch/clear-memory link.
- Add Nginx rate limiting to `/api/resolve` before broad production exposure; the endpoint is not an identity authentication endpoint.
- Only expose the intended Nginx ports. Restrict Octop backend ports to the Nginx server's private IP.
- Current architecture is unified routing followed by per-instance LDAP login; it is not cross-instance SSO.

## 10. Tests

On a Python 3.12+ development environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

The tests use a fake repository and verify routing rules, not live DB connectivity. Database integration must be tested against your actual `nocobase3` and `octop-ldap` databases after deployment.
