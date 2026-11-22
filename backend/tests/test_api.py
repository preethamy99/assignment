import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth import USER_STORE_PATH
from app.main import app


class PackingApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.database_directory.cleanup)
        self.environment = patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "test-signing-key-that-is-at-least-32-bytes",
                "ASSISTANCE_DB_PATH": str(
                    Path(self.database_directory.name) / "assistance.sqlite3"
                ),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self._auth_headers: dict[str, str] | None = None

    @property
    def auth_headers(self) -> dict[str, str]:
        if self._auth_headers is None:
            response = self.client.post(
                "/api/v1/auth/token",
                json={"email": "test@example.com", "password": "1234567890"},
            )
            self.assertEqual(response.status_code, 200)
            self._auth_headers = {
                "Authorization": f"Bearer {response.json()['access_token']}"
            }
        return self._auth_headers

    def test_login_returns_jwt_for_valid_credentials(self) -> None:
        # The demo credentials produce a signed JWT for use by protected endpoints.
        response = self.client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "1234567890"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token_type"], "bearer")
        self.assertTrue(response.json()["access_token"])

    def test_login_rejects_incorrect_password(self) -> None:
        # Incorrect credentials must not issue an access token.
        response = self.client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 401)

    def test_login_validation_does_not_echo_password(self) -> None:
        # Validation errors must not include submitted credentials in responses.
        password = "x" * 129
        response = self.client.post(
            "/api/v1/auth/token",
            json={"email": "test@example.com", "password": password},
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(password, response.text)

    def test_demo_password_is_stored_only_as_a_hash(self) -> None:
        # The static user file must not contain the demo password in plain text.
        user = json.loads(Path(USER_STORE_PATH).read_text(encoding="utf-8"))["users"][0]
        self.assertNotIn("1234567890", json.dumps(user))
        self.assertEqual(len(user["password_hash"]), 64)

    def test_openapi_documents_login_and_bearer_protected_packing(self) -> None:
        # Swagger's schema should expose both requests and packing authorization.
        openapi = self.client.get("/openapi.json").json()
        paths = openapi["paths"]
        self.assertIn("/api/v1/auth/token", paths)
        self.assertIn("/api/v1/pack", paths)
        self.assertIn("/api/v1/assistance-requests", paths)
        self.assertIn("/api/v1/assistance-requests/export", paths)
        self.assertEqual(
            paths["/api/v1/pack"]["post"]["security"],
            [{"HTTPBearer": []}],
        )
        self.assertIn("HTTPBearer", openapi["components"]["securitySchemes"])
        schemas = openapi["components"]["schemas"]
        self.assertIn("boxes", schemas["PackingResult"]["properties"])
        self.assertIn("packages", schemas["BoxAssignment"]["properties"])

    def test_post_returns_box_count_and_package_assignments(self) -> None:
        # These two packages fit together in the smallest available box type.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[
                {"id": 123, "width": 10, "height": 10, "length": 10, "weight": 5},
                {"id": 125, "width": 5, "height": 5, "length": 10, "weight": 10},
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "box_count": 1,
                "boxes": [
                    {
                        "box_number": 1,
                        "box_type": "B",
                        "width": 100.0,
                        "height": 200.0,
                        "length": 100.0,
                        "max_weight": 1000.0,
                        "total_weight": 15.0,
                        "packages": [
                            {
                                "id": 123,
                                "width": 10.0,
                                "height": 10.0,
                                "length": 10.0,
                                "weight": 5.0,
                                "fragile": False,
                            },
                            {
                                "id": 125,
                                "width": 5.0,
                                "height": 5.0,
                                "length": 10.0,
                                "weight": 10.0,
                                "fragile": False,
                            },
                        ],
                    }
                ],
                "special_handling_required": False,
                "special_items": [],
            },
        )

    def test_empty_list_returns_zero(self) -> None:
        # Empty input is valid and requires no boxes.
        response = self.client.post(
            "/api/v1/pack", headers=self.auth_headers, json=[]
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "box_count": 0,
                "boxes": [],
                "special_handling_required": False,
                "special_items": [],
            },
        )

    def test_invalid_dimensions_return_validation_error(self) -> None:
        # Dimensions must be positive, so this request should fail validation.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[{"id": 1, "width": -1, "height": 2, "length": 3, "weight": 4}],
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Invalid package list.")

    def test_unpackable_item_is_returned_for_special_handling(self) -> None:
        # A package larger than Box C is returned separately, not rejected.
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[{"id": 9, "width": 401, "height": 1, "length": 1, "weight": 1}],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["box_count"], 0)
        self.assertEqual(response.json()["boxes"], [])
        self.assertTrue(response.json()["special_handling_required"])
        self.assertEqual(
            response.json()["special_items"],
            [
                {
                    "id": 9,
                    "width": 401.0,
                    "height": 1.0,
                    "length": 1.0,
                    "weight": 1.0,
                    "fragile": False,
                    "reasons": ["oversized"],
                }
            ],
        )

    def test_fragile_item_is_returned_for_special_handling(self) -> None:
        response = self.client.post(
            "/api/v1/pack",
            headers=self.auth_headers,
            json=[
                {
                    "id": 12,
                    "width": 10,
                    "height": 10,
                    "length": 10,
                    "weight": 5,
                    "fragile": True,
                }
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["boxes"], [])
        self.assertEqual(
            response.json()["special_items"][0]["reasons"],
            ["fragile"],
        )

    def test_assistance_request_is_saved_with_contact_and_order_details(self) -> None:
        payload = {
            "contact_name": "Alex Customer",
            "contact_email": "alex@example.com",
            "contact_phone": "+1 555-0100",
            "notes": "Please handle the glass item carefully.",
            "packages": [
                {"id": 1, "width": 10, "height": 10, "length": 10, "weight": 5},
                {
                    "id": 2,
                    "width": 10,
                    "height": 10,
                    "length": 10,
                    "weight": 5,
                    "fragile": True,
                },
                {"id": 3, "width": 401, "height": 1, "length": 1, "weight": 1},
                {"id": 4, "width": 10, "height": 10, "length": 10, "weight": 3001},
            ],
        }
        response = self.client.post(
            "/api/v1/assistance-requests",
            headers=self.auth_headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 201)
        receipt = response.json()
        self.assertEqual(receipt["status"], "submitted")
        self.assertTrue(receipt["request_id"])

        review = self.client.get(
            "/api/v1/assistance-requests",
            headers=self.auth_headers,
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(len(review.json()), 1)
        record = review.json()[0]
        self.assertEqual(record["request_id"], receipt["request_id"])
        self.assertEqual(record["contact_name"], "Alex Customer")
        self.assertEqual(record["contact_email"], "alex@example.com")
        self.assertEqual(record["contact_phone"], "+1 555-0100")
        self.assertEqual(record["notes"], payload["notes"])
        self.assertEqual(record["box_count"], 1)
        self.assertEqual(record["boxes"][0]["packages"][0]["id"], 1)
        self.assertEqual(
            [item["id"] for item in record["special_items"]],
            [2, 3, 4],
        )
        self.assertEqual(
            [item["reasons"] for item in record["special_items"]],
            [["fragile"], ["oversized"], ["overweight"]],
        )

        export = self.client.get(
            "/api/v1/assistance-requests/export",
            headers=self.auth_headers,
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("attachment; filename=", export.headers["content-disposition"])
        self.assertIn("alex@example.com", export.text)
        self.assertIn("assistance required", export.text)
        self.assertIn("overweight", export.text)

    def test_assistance_request_requires_at_least_one_special_item(self) -> None:
        response = self.client.post(
            "/api/v1/assistance-requests",
            headers=self.auth_headers,
            json={
                "contact_name": "Alex Customer",
                "contact_email": "alex@example.com",
                "contact_phone": "+1 555-0100",
                "packages": [
                    {
                        "id": 1,
                        "width": 10,
                        "height": 10,
                        "length": 10,
                        "weight": 5,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "This order has no items requiring special handling.",
        )

    def test_assistance_request_validation_does_not_echo_contact_data(self) -> None:
        phone = "x" * 40
        response = self.client.post(
            "/api/v1/assistance-requests",
            headers=self.auth_headers,
            json={
                "contact_name": "Alex Customer",
                "contact_email": "alex@example.com",
                "contact_phone": phone,
                "packages": [
                    {
                        "id": 1,
                        "width": 10,
                        "height": 10,
                        "length": 10,
                        "weight": 5,
                        "fragile": True,
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(phone, response.text)

    def test_assistance_request_endpoints_require_jwt(self) -> None:
        review = self.client.get("/api/v1/assistance-requests")
        export = self.client.get("/api/v1/assistance-requests/export")
        self.assertEqual(review.status_code, 401)
        self.assertEqual(export.status_code, 401)

    def test_missing_token_returns_401(self) -> None:
        # Protected endpoints reject requests without a JWT.
        response = self.client.post("/api/v1/pack", json=[])
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["www-authenticate"], "Bearer")

    def test_invalid_token_returns_401(self) -> None:
        # Arbitrary bearer values are not accepted as signed JWTs.
        response = self.client.post(
            "/api/v1/pack",
            headers={"Authorization": "Bearer not-a-jwt"},
            json=[],
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_signing_secret_returns_503(self) -> None:
        # The service must not issue or verify tokens without a strong signing key.
        del os.environ["JWT_SECRET_KEY"]
        response = self.client.post(
            "/api/v1/pack",
            headers={"Authorization": "Bearer arbitrary"},
            json=[],
        )
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
