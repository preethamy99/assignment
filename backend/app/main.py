import csv
import io
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth import get_current_user, router as auth_router
from app.assistance_store import load_requests, save_request
from app.packing import PackedBox, Package as PackingPackage
from app.packing import PackingPlan, SpecialHandlingItem, SpecialHandlingReason
from app.packing import UnpackablePackageError, plan_packages

app = FastAPI(
    title="Shipping Box Calculator API",
    version="1.0.0",
    description=(
        "Calculate box assignments and identify items requiring special handling. "
        "Sign in at `/api/v1/auth/token` to receive a JWT before calling "
        "protected endpoints."
    ),
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Sign in and issue short-lived JWT access tokens.",
        },
        {
            "name": "assistance",
            "description": "Submit and review special-handling requests.",
        },
    ],
)
app.include_router(auth_router)


class PackageInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "id": 123,
                "width": 10,
                "height": 10,
                "length": 10,
                "weight": 5,
                "fragile": False,
            }
        },
    )

    id: int
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    length: float = Field(gt=0, allow_inf_nan=False)
    weight: float = Field(ge=0, allow_inf_nan=False)
    fragile: bool = False


class PackageAssignment(BaseModel):
    id: int
    width: float
    height: float
    length: float
    weight: float
    fragile: bool


class BoxAssignment(BaseModel):
    box_number: int
    box_type: Literal["A", "B", "C"]
    width: float
    height: float
    length: float
    max_weight: float
    total_weight: float
    packages: list[PackageAssignment]


class SpecialHandlingAssignment(BaseModel):
    id: int
    width: float
    height: float
    length: float
    weight: float
    fragile: bool
    reasons: list[SpecialHandlingReason]


class PackingResult(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
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
                                "fragile": False,
                            },
                            {
                                "id": 125,
                                "width": 5,
                                "height": 5,
                                "length": 10,
                                "weight": 10,
                                "fragile": False,
                            },
                        ],
                    }
                ],
                "special_handling_required": False,
                "special_items": [],
            }
        }
    )

    box_count: int
    boxes: list[BoxAssignment]
    special_handling_required: bool
    special_items: list[SpecialHandlingAssignment]


class AssistanceRequestSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: str = Field(min_length=1, max_length=1000)
    packages: list[PackageInput] = Field(min_length=1, max_length=500)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("An order note is required.")
        return normalized


class AssistanceRequestReceipt(BaseModel):
    request_id: str
    submitted_at: str
    status: Literal["submitted"]


class AssistanceRequestRecord(AssistanceRequestReceipt):
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None
    box_count: int
    boxes: list[BoxAssignment]
    special_handling_required: bool
    special_items: list[SpecialHandlingAssignment]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    is_packing_request = _request.url.path == "/api/v1/pack"
    detail = "Invalid package list." if is_packing_request else "Invalid request."
    errors = exc.errors()
    if _request.url.path in {
        "/api/v1/auth/token",
        "/api/v1/assistance-requests",
    }:
        errors = [
            {key: value for key, value in error.items() if key != "input"}
            for error in errors
        ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": detail,
            "errors": jsonable_encoder(errors),
        },
    )


@app.exception_handler(UnpackablePackageError)
async def unpackable_exception_handler(
    _request: Request, exc: UnpackablePackageError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "message": str(exc),
                "package_id": exc.package_id,
            }
        },
    )


@app.post(
    "/api/v1/pack",
    response_model=PackingResult,
    summary="Calculate boxes and package assignments",
    description=(
        "Accept a JSON array of packages. Dimensions must be positive and "
        "weights non-negative. Packages may be rotated. Fragile, overweight, "
        "and oversized packages are returned separately for assistance."
    ),
    response_description=(
        "The box count, package assignments, and any special-handling items."
    ),
    responses={
        401: {"description": "A valid JWT bearer token is required."},
        422: {"description": "Invalid package data."},
        503: {"description": "JWT signing is not securely configured."},
    },
)
def calculate_boxes(
    packages: list[PackageInput], _user: str = Depends(get_current_user)
) -> PackingResult:
    plan = plan_packages([_to_packing_package(package) for package in packages])
    return _to_packing_result(plan)


@app.post(
    "/api/v1/assistance-requests",
    response_model=AssistanceRequestReceipt,
    status_code=201,
    tags=["assistance"],
    summary="Submit an assistance request",
    description=(
        "Save a required order note and a backend-calculated snapshot for "
        "fragile, overweight, or oversized packages. The authenticated account "
        "email is recorded automatically."
    ),
    responses={
        401: {"description": "A valid JWT bearer token is required."},
        422: {
            "description": (
                "A required order note or package data is invalid, or no item "
                "requires assistance."
            )
        },
        503: {"description": "JWT signing is not securely configured."},
    },
)
def submit_assistance_request(
    submission: AssistanceRequestSubmission,
    _user: str = Depends(get_current_user),
) -> AssistanceRequestReceipt:
    plan = plan_packages(
        [_to_packing_package(package) for package in submission.packages]
    )
    if not plan.special_items:
        raise HTTPException(
            status_code=422,
            detail="This order has no items requiring special handling.",
        )

    request_id = str(uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat()
    record = _to_assistance_record(
        request_id, submitted_at, _user, submission, plan
    )
    save_request(request_id, submitted_at, record.model_dump_json())
    return AssistanceRequestReceipt(
        request_id=request_id,
        submitted_at=submitted_at,
        status="submitted",
    )


@app.get(
    "/api/v1/assistance-requests",
    response_model=list[AssistanceRequestRecord],
    tags=["assistance"],
    summary="Review submitted assistance requests",
    description="Return stored requests and their complete order snapshots.",
    responses={
        401: {"description": "A valid JWT bearer token is required."},
        503: {"description": "JWT signing is not securely configured."},
    },
)
def list_assistance_requests(
    _user: str = Depends(get_current_user),
) -> list[AssistanceRequestRecord]:
    return [
        AssistanceRequestRecord.model_validate(request)
        for request in load_requests()
    ]


@app.get(
    "/api/v1/assistance-requests/export",
    tags=["assistance"],
    summary="Export assistance requests as CSV",
    responses={
        401: {"description": "A valid JWT bearer token is required."},
        503: {"description": "JWT signing is not securely configured."},
    },
)
def export_assistance_requests(
    _user: str = Depends(get_current_user),
) -> StreamingResponse:
    records = list_assistance_requests(_user)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "request_id",
            "submitted_at",
            "contact_name",
            "contact_email",
            "contact_phone",
            "notes",
            "item_status",
            "box_number",
            "box_type",
            "package_id",
            "width",
            "height",
            "length",
            "weight",
            "fragile",
            "handling_reasons",
        ]
    )
    for record in records:
        for box in record.boxes:
            for package in box.packages:
                writer.writerow(
                    _assistance_csv_row(
                        record,
                        "packed",
                        box.box_number,
                        box.box_type,
                        package,
                        [],
                    )
                )
        for item in record.special_items:
            writer.writerow(
                _assistance_csv_row(
                    record,
                    "assistance required",
                    "",
                    "",
                    item,
                    item.reasons,
                )
            )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="assistance-requests.csv"'
        },
    )


def _to_packing_package(package: PackageInput) -> PackingPackage:
    return PackingPackage(
        id=package.id,
        width=package.width,
        height=package.height,
        length=package.length,
        weight=package.weight,
        fragile=package.fragile,
    )


def _to_packing_result(plan: PackingPlan) -> PackingResult:
    return PackingResult(
        box_count=len(plan.boxes),
        boxes=[_to_box_assignment(box) for box in plan.boxes],
        special_handling_required=bool(plan.special_items),
        special_items=[
            _to_special_handling_assignment(item) for item in plan.special_items
        ],
    )


def _to_assistance_record(
    request_id: str,
    submitted_at: str,
    submitted_by: str,
    submission: AssistanceRequestSubmission,
    plan: PackingPlan,
) -> AssistanceRequestRecord:
    return AssistanceRequestRecord(
        request_id=request_id,
        submitted_at=submitted_at,
        status="submitted",
        contact_email=submitted_by,
        notes=submission.notes,
        box_count=len(plan.boxes),
        boxes=[_to_box_assignment(box) for box in plan.boxes],
        special_handling_required=bool(plan.special_items),
        special_items=[
            _to_special_handling_assignment(item) for item in plan.special_items
        ],
    )


def _to_box_assignment(box: PackedBox) -> BoxAssignment:
    return BoxAssignment(
        box_number=box.box_number,
        box_type=box.box_type.name,
        width=box.box_type.width,
        height=box.box_type.height,
        length=box.box_type.length,
        max_weight=box.box_type.max_weight,
        total_weight=box.total_weight,
        packages=[
            PackageAssignment(
                id=package.id,
                width=package.width,
                height=package.height,
                length=package.length,
                weight=package.weight,
                fragile=package.fragile,
            )
            for package in box.packages
        ],
    )


def _to_special_handling_assignment(
    item: SpecialHandlingItem,
) -> SpecialHandlingAssignment:
    package = item.package
    return SpecialHandlingAssignment(
        id=package.id,
        width=package.width,
        height=package.height,
        length=package.length,
        weight=package.weight,
        fragile=package.fragile,
        reasons=list(item.reasons),
    )


def _assistance_csv_row(
    record: AssistanceRequestRecord,
    item_status: str,
    box_number: int | str,
    box_type: str,
    package: PackageAssignment | SpecialHandlingAssignment,
    reasons: list[str] | list[SpecialHandlingReason],
) -> list[str | int | float | bool]:
    return [
        record.request_id,
        record.submitted_at,
        record.contact_name or "",
        record.contact_email or "",
        record.contact_phone or "",
        record.notes or "",
        item_status,
        box_number,
        box_type,
        package.id,
        package.width,
        package.height,
        package.length,
        package.weight,
        package.fragile,
        "; ".join(reasons),
    ]
