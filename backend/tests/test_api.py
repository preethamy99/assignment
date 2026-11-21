import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class PackingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {"API_AUTH_TOKEN": "test-secret"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(app)
        self.auth_headers = {"Authorization": "Bearer test-secret"}

    def test_post_returns_box_count(self) -> None:
        # These two packages should share one box.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[
                {"id": 123, "width": 10, "height": 10, "length": 10, "weight": 5},
                {"id": 125, "width": 5, "height": 5, "length": 10, "weight": 10},
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"box_count": 1})

    def test_empty_list_returns_zero(self) -> None:
        # Empty input is valid and requires no boxes.
        response = self.client.post(
            "/api/v1/pack", headers=self.auth_headers, json=[]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"box_count": 0})

    def test_invalid_dimensions_return_validation_error(self) -> None:
        # Dimensions must be positive, so this request should fail validation.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[{"id": 1, "width": -1, "height": 2, "length": 3, "weight": 4}],
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Invalid package list.")

    def test_unpackable_item_returns_422_with_package_id(self) -> None:
        # A package larger than every available box should be identified.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[{"id": 9, "width": 401, "height": 1, "length": 1, "weight": 1}],
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["package_id"], 9)

    def test_missing_token_returns_401(self) -> None:
        # The endpoint must reject requests without bearer credentials.
        response = self.client.post("/api/v1/pack", json=[])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_invalid_token_returns_401(self) -> None:
        # A well-formed but incorrect bearer token must not grant access.
        response = self.client.post(
            "/api/v1/pack",
            headers={"Authorization": "Bearer wrong-secret"},
            json=[],
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_server_token_configuration_returns_503(self) -> None:
        # An unset server secret must fail closed rather than allow access.
        del os.environ["API_AUTH_TOKEN"]
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[],
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
