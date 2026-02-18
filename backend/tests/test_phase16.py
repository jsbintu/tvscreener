"""
Bubby Vision — Phase 16 Tests

Tests for:
- Swagger UI customization
- API documentation completeness
- Load testing configuration
"""

import pytest


# ════════════════════════════════════════════════
#  SWAGGER UI CUSTOMIZATION
# ════════════════════════════════════════════════


class TestSwaggerUI:

    def _get_client(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        return TestClient(create_app())

    def _get_app(self):
        from app.main import create_app
        return create_app()

    def test_docs_endpoint_accessible(self):
        resp = self._get_client().get("/docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_redoc_endpoint_accessible(self):
        resp = self._get_client().get("/redoc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_openapi_json_accessible(self):
        resp = self._get_client().get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["info"]["title"] == "Bubby Vision"

    def test_api_version_is_1_0_0(self):
        resp = self._get_client().get("/openapi.json")
        data = resp.json()
        assert data["info"]["version"] == "1.0.0"

    def test_description_contains_features(self):
        resp = self._get_client().get("/openapi.json")
        data = resp.json()
        desc = data["info"]["description"]
        assert "Real-time Market Data" in desc
        assert "AI Analysis" in desc
        assert "WebSocket Streams" in desc
        assert "OWASP Hardened" in desc

    def test_contact_info_present(self):
        resp = self._get_client().get("/openapi.json")
        data = resp.json()
        assert "contact" in data["info"]
        assert data["info"]["contact"]["name"] == "Bubby Vision Team"

    def test_license_info_present(self):
        resp = self._get_client().get("/openapi.json")
        data = resp.json()
        assert "license" in data["info"]
        assert data["info"]["license"]["name"] == "MIT"

    def test_swagger_ui_parameters(self):
        """Verify custom Swagger UI parameters are set."""
        app = self._get_app()
        params = app.swagger_ui_parameters
        assert params["deepLinking"] is True
        assert params["persistAuthorization"] is True
        assert params["displayRequestDuration"] is True
        assert params["filter"] is True


# ════════════════════════════════════════════════
#  OPENAPI TAGS
# ════════════════════════════════════════════════


class TestOpenAPITags:

    def test_all_tags_present(self):
        from fastapi.testclient import TestClient
        from app.main import create_app

        client = TestClient(create_app())
        resp = client.get("/openapi.json")
        data = resp.json()
        tag_names = [t["name"] for t in data.get("tags", [])]

        expected_tags = [
            "Health", "Data", "Chat", "Market Data", "Live Options",
            "Alpaca Market Data", "Extended Data", "Watchlist & Alerts",
            "External Links", "WebSocket", "Metrics", "Audit",
        ]
        for tag in expected_tags:
            assert tag in tag_names, f"Missing OpenAPI tag: {tag}"

    def test_tags_have_descriptions(self):
        from fastapi.testclient import TestClient
        from app.main import create_app

        client = TestClient(create_app())
        resp = client.get("/openapi.json")
        data = resp.json()

        for tag_obj in data.get("tags", []):
            assert "description" in tag_obj, f"Tag {tag_obj['name']} missing description"
            assert len(tag_obj["description"]) > 10


# ════════════════════════════════════════════════
#  LOAD TESTING CONFIG
# ════════════════════════════════════════════════


class TestLoadTestConfig:

    def test_locustfile_exists(self):
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "locustfile.py"
        )
        assert os.path.exists(path)

    def test_locustfile_has_user_class(self):
        """The locust file should define a HttpUser subclass."""
        import importlib.util
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "locustfile.py"
        )
        spec = importlib.util.spec_from_file_location("locustfile", path)
        mod = importlib.util.module_from_spec(spec)

        # Don't actually exec (requires locust), just verify the file parses
        import ast
        with open(path) as f:
            tree = ast.parse(f.read())

        class_names = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        assert "Bubby VisionUser" in class_names

    def test_locustfile_has_tasks(self):
        """The locust file should define multiple @task methods."""
        import ast
        import os

        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "locustfile.py"
        )

        with open(path) as f:
            tree = ast.parse(f.read())

        # Count methods with @task decorator
        task_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == "task":
                        task_count += 1
                    elif isinstance(dec, ast.Name) and dec.id == "task":
                        task_count += 1

        assert task_count >= 10, f"Expected at least 10 load test tasks, found {task_count}"
