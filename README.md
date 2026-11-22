# Shipping Box Calculator

A FastAPI service that estimates the number of shipping boxes needed for a list
of packages and reports which packages are assigned to each box.

## Requirements

- Python 3.10+

## Set up, run, and test

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env
$secret = python -c "import secrets; print(secrets.token_urlsafe(48))"
Set-Content .env "JWT_SECRET_KEY=$secret"
Set-Location backend
python -m uvicorn app.main:app --reload --env-file ..\.env
```

The API is available at `http://127.0.0.1:8000`; interactive API documentation
is at `http://127.0.0.1:8000/docs` (Swagger UI), `/redoc` (ReDoc), and
`/openapi.json` (OpenAPI schema). The `.env` file is local and Git-ignored; do
not share it. JWTs expire after 30 minutes.

In another terminal, run the tests from the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

## API

### Swagger and Postman

The running API serves interactive Swagger documentation at
`http://127.0.0.1:8000/docs`. The OpenAPI schema is also available at
`http://127.0.0.1:8000/openapi.json`. In Swagger, run the login endpoint, copy
`access_token`, click **Authorize**, and paste the token to try the protected
packing endpoint.

Import [collection.json](./collection.json) into Postman. Set its `baseUrl`
collection variable if the backend is not at `http://127.0.0.1:8000`, then set
the `password` variable to the demo password. Run **Authentication → Sign in
and save JWT** first; its test script saves the returned JWT. Then run
**Packing → Calculate box count**, which attaches the JWT automatically.

### Sign in

`POST /api/v1/auth/token` accepts the demo account credentials:

```json
{
  "email": "test@example.com",
  "password": "1234567890"
}
```

The endpoint returns a signed JWT:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

The password is stored as a salted PBKDF2 hash in `backend/app/static.json`,
not as plain text. This fixed demo account and password are for local
development only; replace the demo account and use managed user storage before
deploying the service.

### Calculate boxes

`POST /api/v1/pack` accepts a JSON array:

```json
[
  {
    "id": 123,
    "width": 10,
    "height": 10,
    "length": 10,
    "weight": 5,
    "fragile": false
  },
  {
    "id": 125,
    "width": 5,
    "height": 5,
    "length": 10,
    "weight": 10,
    "fragile": false
  }
]
```

Successful response:

```json
{
  "box_count": 1,
  "boxes": [
    {
      "box_number": 1,
      "box_type": "B",
      "width": 100,
      "height": 200,
      "length": 100,
      "max_weight": 1000,
      "total_weight": 15,
      "packages": [
        {
          "id": 123,
          "width": 10,
          "height": 10,
          "length": 10,
          "weight": 5,
          "fragile": false
        },
        {
          "id": 125,
          "width": 5,
          "height": 5,
          "length": 10,
          "weight": 10,
          "fragile": false
        }
      ]
    }
  ],
  "special_handling_required": false,
  "special_items": []
}
```

`box_count` matches the number of entries in `boxes`. Each entry includes its
box number, catalogue type and limits, total weight, and the complete package
records assigned to it. An empty array returns zero boxes and an empty
`special_items` array.

Requests to `/api/v1/pack` must include the JWT in the standard authorization
header:

```text
Authorization: Bearer <access_token>
```

Missing or invalid credentials return HTTP 401. If `JWT_SECRET_KEY` is not set
or is shorter than 32 characters, the service returns HTTP 503 rather than
issuing or accepting tokens.

For Postman, first send the login request and copy `access_token`. Then, on the
packing request, open **Authorization**, select **Bearer Token**, and paste the
JWT. Alternatively, add the header manually as shown above.

Invalid package data returns HTTP 422. Fragile packages (`fragile: true`),
packages too large to fit Box C in any rotation, and packages weighing over
3,000 are returned in `special_items`; these are excluded from `box_count` and
the standard box assignments. The response includes a reason for each item.

### Request special handling

When the packing response contains special items, the frontend can submit the
customer's contact information and the package list to
`POST /api/v1/assistance-requests`. The customer's name, email, phone, package
details, standard box assignments, and special-handling reasons are stored
together as one order snapshot in SQLite. A generated `request_id` is returned
as the reference for that request.

```json
{
  "contact_name": "Alex Customer",
  "contact_email": "alex@example.com",
  "contact_phone": "+1 555-0100",
  "notes": "Please review the glass item.",
  "packages": [
    { "id": 123, "width": 10, "height": 10, "length": 10, "weight": 5 },
    {
      "id": 901,
      "width": 10,
      "height": 10,
      "length": 10,
      "weight": 5,
      "fragile": true
    }
  ]
}
```

The endpoint returns HTTP 201 when the request is saved. Contact name, email,
and phone are required; notes are optional. Requests without at least one
special-handling item are rejected. The protected
`GET /api/v1/assistance-requests` endpoint lists stored order snapshots for
follow-up, and `GET /api/v1/assistance-requests/export` downloads them as CSV.
The SQLite database defaults to `backend/data/assistance_requests.sqlite3`;
set `ASSISTANCE_DB_PATH` to use another path. The review/export endpoints use
the current JWT authentication; configure staff-specific authorization before
deploying with real customer data.

## Approach and assumptions

- Package dimensions must be positive; weight must be non-negative. IDs are
  integers, and extra fields are rejected. The optional `fragile` field
  defaults to `false`.
- A package may be rotated. Packages in the same box must have non-overlapping,
  axis-aligned placements inside the box, and their combined weight must not
  exceed the box limit.
- Fragile items, items that cannot fit Box C in any rotation, and items over
  Box C's 3,000 weight limit are separated from the standard packing plan for
  special handling.
- The catalogue is in `backend/app/packing.py`. Box C is at least as large in
  every dimension and has greater weight capacity than A and B. The service
  first packs into C-sized bins to prioritize the fewest boxes, then uses the
  smallest catalogue type that can fit each bin's existing package group
  without adding boxes. This type-selection step uses the same placement
  heuristic and may not find every possible smaller arrangement.
- Packages are considered in descending volume and weight. For each package,
  the service chooses the best-fitting available free space using a
  three-dimensional guillotine split heuristic. The response reports package
  assignments, not precise 3D placement coordinates; the heuristic is not
  guaranteed to find a globally minimal arrangement.
- Packing calculations remain stateless. SQLite is used only to persist
  assistance requests and their customer/order snapshots in
  `backend/data/assistance_requests.sqlite3`.

With more time, I would compare the heuristic against a broader set of packing
fixtures and add property-based tests for placement invariants.
Add realtime metrics for obseravality.

## Frontend

The Angular application lives in `frontend/`. Start the backend, then run in
another PowerShell terminal:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd start
```

Open `http://localhost:4200`, sign in with the demo account, edit the sample
packages or add your own, or import `.csv`, `.xls`, or `.xlsx` files. Imports
append to the current list and read the first worksheet; required column
headers are `id`, `width`, `height`, `length`, and `weight`. An optional
`fragile` column accepts true/false values and defaults to false. Files are
limited to 10 MB and 500 packages total. Use the
[CSV template](./frontend/public/package-template.csv) as a starting point.
The frontend fetches the JWT during sign-in and attaches it automatically to
packing and assistance requests. The token remains in memory and expires
after 30 minutes. The Angular development-server proxy forwards `/api`
requests to the local FastAPI service at `http://127.0.0.1:8000`. The summary
shows standard box assignments and separates special-handling items. Customers
can submit their required contact details; the team can review requests through
the protected API or export them as CSV.

Run frontend checks from `frontend/`:

```powershell
npm.cmd test -- --watch=false
npm.cmd run build
```

## Run the backend in Docker

With Docker Desktop running and `.env` created at the repository root, build
and start the backend from that root:

```powershell
docker build -t shipping-box-backend -f backend\Dockerfile .
docker run --rm --name shipping-box-api -p 8000:8000 --env-file .env `
  --mount source=shipping-box-data,target=/app/data shipping-box-backend
```

The container reads `JWT_SECRET_KEY` from `.env`; the secret is not copied into
the image. The named `shipping-box-data` volume preserves SQLite assistance
requests across container runs. Open `http://127.0.0.1:8000/docs` to try the
API. Stop the container with **Ctrl+C**. To run it in the background instead,
add `-d` to `docker run` and stop it later with `docker stop shipping-box-api`.
