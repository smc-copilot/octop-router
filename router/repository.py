"""Read-only PostgreSQL repositories for NocoBase identity and Octop registry.

The Router talks to two separate PostgreSQL databases:
- nocobase3: public.v_octop_user_routes
- octop-ldap: public.octop_applications, public.octop_databases,
  public.octop_application_databases

It never reads passwords, LDAP credentials, Octop JWTs, or Octop operational DBs.
"""
from __future__ import annotations

import os
from typing import Any


class RepositoryConfigurationError(RuntimeError):
    """Required database connection settings are missing or invalid."""


class RepositoryUnavailable(RuntimeError):
    """A configured PostgreSQL database could not be queried."""


class RouteNotFound(RuntimeError):
    """No active Octop application assignment exists for the employee."""


class InvalidAssignment(RuntimeError):
    """The employee or Octop registry contains an ambiguous/invalid mapping."""


class PostgresRouterRepository:
    """Two read-only PostgreSQL connections, one per database."""

    USER_ROUTES_SQL = """
        SELECT employee_no, app_code, is_default
          FROM public.v_octop_user_routes
         WHERE employee_no = %s
           AND is_active IS TRUE
         ORDER BY is_default DESC, app_code ASC
    """

    APPLICATIONS_SQL = """
        SELECT a.app_code,
               a.public_url,
               a.nginx_port,
               a.status AS app_status,
               COUNT(d.id) FILTER (
                   WHERE ad.relation_type = 'primary'
                     AND ad.is_primary IS TRUE
                     AND ad.status = 'enabled'
                     AND d.status = 'enabled'
               ) AS active_primary_database_count
          FROM public.octop_applications AS a
          LEFT JOIN public.octop_application_databases AS ad
                 ON ad.application_id = a.id
          LEFT JOIN public.octop_databases AS d
                 ON d.id = ad.database_id
         WHERE a.app_code = ANY(%s)
         GROUP BY a.id, a.app_code, a.public_url, a.nginx_port, a.status
    """

    def __init__(self, nocobase_dsn: str | None = None, octop_ldap_dsn: str | None = None):
        self.nocobase_dsn = nocobase_dsn or os.getenv("NOCOBASE_DATABASE_URL", "")
        self.octop_ldap_dsn = octop_ldap_dsn or os.getenv("OCTOP_LDAP_DATABASE_URL", "")
        if not self.nocobase_dsn or not self.octop_ldap_dsn:
            raise RepositoryConfigurationError(
                "NOCOBASE_DATABASE_URL and OCTOP_LDAP_DATABASE_URL must both be configured"
            )

    @staticmethod
    def _connect(dsn: str):
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on deployment image
            raise RepositoryConfigurationError("psycopg is not installed") from exc
        try:
            return psycopg.connect(
                dsn,
                connect_timeout=int(os.getenv("PGCONNECT_TIMEOUT", "5")),
                options=(
                    "-c default_transaction_read_only=on "
                    "-c statement_timeout=5000 "
                    "-c idle_in_transaction_session_timeout=5000"
                ),
            )
        except Exception as exc:
            # Do not include DSNs or exception strings; they can contain credentials.
            raise RepositoryUnavailable("PostgreSQL connection failed") from exc

    def get_user_assignments(self, employee_no: str) -> list[dict[str, Any]]:
        try:
            with self._connect(self.nocobase_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(self.USER_ROUTES_SQL, (employee_no,))
                    rows = cur.fetchall()
            return [
                {
                    "employee_no": str(row[0]),
                    "app_code": str(row[1]),
                    "is_default": bool(row[2]),
                }
                for row in rows
            ]
        except (RepositoryConfigurationError, RepositoryUnavailable):
            raise
        except Exception as exc:
            raise RepositoryUnavailable("NocoBase route lookup failed") from exc

    def get_applications(self, app_codes: list[str]) -> dict[str, dict[str, Any]]:
        if not app_codes:
            return {}
        try:
            with self._connect(self.octop_ldap_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(self.APPLICATIONS_SQL, (app_codes,))
                    rows = cur.fetchall()
            return {
                str(row[0]): {
                    "app_code": str(row[0]),
                    "public_url": str(row[1]),
                    "nginx_port": int(row[2]),
                    "status": str(row[3]),
                    "active_primary_database_count": int(row[4]),
                }
                for row in rows
            }
        except (RepositoryConfigurationError, RepositoryUnavailable):
            raise
        except Exception as exc:
            raise RepositoryUnavailable("Octop application registry lookup failed") from exc

    def health(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name, dsn in (
            ("nocobase", self.nocobase_dsn),
            ("octop_ldap", self.octop_ldap_dsn),
        ):
            try:
                with self._connect(dsn) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                result[name] = "ok"
            except Exception:
                result[name] = "error"
        return result


def resolve_target(
    repository: Any,
    employee_no: str,
    expected_host: str,
    allowed_ports: set[int],
) -> dict[str, str]:
    """Resolve employee -> authorized app -> registered and allowlisted URL."""
    assignments = repository.get_user_assignments(employee_no)
    if not assignments:
        raise RouteNotFound("no active Octop application assignment")

    app_codes = [str(row["app_code"]) for row in assignments]
    if any(not code for code in app_codes) or len(app_codes) != len(set(app_codes)):
        raise InvalidAssignment("empty or duplicate user/application assignment")

    defaults = [row for row in assignments if bool(row["is_default"])]
    if len(assignments) == 1:
        selected = assignments[0]
    elif len(defaults) == 1:
        selected = defaults[0]
    else:
        raise InvalidAssignment("multiple application assignments require exactly one default")

    apps = repository.get_applications(app_codes)
    app = apps.get(str(selected["app_code"]))
    if not app or app.get("status") != "enabled":
        raise InvalidAssignment("assigned Octop application is missing or disabled")
    if app.get("active_primary_database_count") != 1:
        raise InvalidAssignment("Octop application must have exactly one enabled primary database")

    from urllib.parse import urlsplit

    url = str(app.get("public_url", ""))
    parsed = urlsplit(url)
    try:
        url_port = parsed.port
    except ValueError as exc:
        raise InvalidAssignment("invalid registered Octop URL port") from exc

    registered_port = app.get("nginx_port")
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != expected_host.lower()
        or url_port not in allowed_ports
        or registered_port != url_port
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise InvalidAssignment("registered Octop URL is outside the approved host/port allowlist")

    return {
        "target": f"https://{expected_host}:{url_port}/",
        "app_code": str(selected["app_code"]),
    }
