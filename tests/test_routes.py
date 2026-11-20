import unittest
from fastapi.testclient import TestClient

from router.app import app
from router.repository import InvalidAssignment, RouteNotFound, resolve_target


class FakeRepository:
    def __init__(self):
        self.assignments = {
            "001234": [{"employee_no": "001234", "app_code": "octop-bc02", "is_default": True}],
            "e10004": [
                {"employee_no": "e10004", "app_code": "octop-bc01", "is_default": False},
                {"employee_no": "e10004", "app_code": "octop-bc02", "is_default": True},
            ],
            "multidef": [
                {"employee_no": "multidef", "app_code": "octop-bc01", "is_default": True},
                {"employee_no": "multidef", "app_code": "octop-bc02", "is_default": True},
            ],
            "nodefault": [
                {"employee_no": "nodefault", "app_code": "octop-bc01", "is_default": False},
                {"employee_no": "nodefault", "app_code": "octop-bc02", "is_default": False},
            ],
        }
        self.apps = {
            "octop-bc01": {
                "app_code": "octop-bc01", "public_url": "https://ai.superice.com:8091/",
                "nginx_port": 8091, "status": "enabled", "active_primary_database_count": 1,
            },
            "octop-bc02": {
                "app_code": "octop-bc02", "public_url": "https://ai.superice.com:8092/",
                "nginx_port": 8092, "status": "enabled", "active_primary_database_count": 1,
            },
        }

    def get_user_assignments(self, employee_no):
        rows = self.assignments.get(employee_no, [])
        if not rows:
            raise RouteNotFound()
        return rows

    def get_applications(self, app_codes):
        return {code: self.apps[code] for code in app_codes if code in self.apps}

    def health(self):
        return {"nocobase": "ok", "octop_ldap": "ok"}


class RouterTests(unittest.TestCase):
    def setUp(self):
        app.state.repository = FakeRepository()
        self.client = TestClient(app)

    def tearDown(self):
        app.state.repository = None

    def test_health(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)

    def test_single_assignment_and_leading_zero_preserved(self):
        response = self.client.post("/api/resolve", json={"employee_id": "001234"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["target"], "https://ai.superice.com:8092/")

    def test_multiple_assignment_default_and_lowercase_normalization(self):
        response = self.client.post("/api/resolve", json={"employee_id": "E10004"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["app_code"], "octop-bc02")

    def test_no_assignment(self):
        self.assertEqual(self.client.post("/api/resolve", json={"employee_id": "UNKNOWN"}).status_code, 404)

    def test_multiple_defaults_rejected(self):
        self.assertEqual(self.client.post("/api/resolve", json={"employee_id": "MULTIDEF"}).status_code, 409)

    def test_multiple_assignments_without_default_rejected(self):
        self.assertEqual(self.client.post("/api/resolve", json={"employee_id": "NODEFAULT"}).status_code, 409)

    def test_no_domain_prefix_normalization(self):
        self.assertEqual(self.client.post("/api/resolve", json={"employee_id": r"DOMAIN\001234"}).status_code, 400)

    def test_no_whitespace_normalization(self):
        self.assertEqual(self.client.post("/api/resolve", json={"employee_id": " 001234"}).status_code, 400)

    def test_unapproved_url_rejected(self):
        repo = FakeRepository()
        repo.apps["octop-bc02"]["public_url"] = "https://evil.example:8092/"
        with self.assertRaises(InvalidAssignment):
            resolve_target(repo, "001234", "ai.superice.com", set(range(8091, 8101)))

    def test_nginx_port_must_match_public_url(self):
        repo = FakeRepository()
        repo.apps["octop-bc02"]["nginx_port"] = 8091
        with self.assertRaises(InvalidAssignment):
            resolve_target(repo, "001234", "ai.superice.com", set(range(8091, 8101)))

    def test_missing_primary_database_rejected(self):
        repo = FakeRepository()
        repo.apps["octop-bc02"]["active_primary_database_count"] = 0
        with self.assertRaises(InvalidAssignment):
            resolve_target(repo, "001234", "ai.superice.com", set(range(8091, 8101)))

    def test_unknown_app_rejected(self):
        repo = FakeRepository()
        repo.assignments["ghost"] = [{"employee_no": "ghost", "app_code": "missing", "is_default": True}]
        with self.assertRaises(InvalidAssignment):
            resolve_target(repo, "ghost", "ai.superice.com", set(range(8091, 8101)))

    def test_api_rejects_extra_fields(self):
        response = self.client.post("/api/resolve", json={"employee_id": "001234", "password": "not-accepted"})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
