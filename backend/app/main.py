from typing import Literal

from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import get_current_user, router as auth_router
from app.packing import PackedBox, Package as PackingPackage
from app.packing import UnpackablePackageError, pack_packages

app = FastAPI(
    title="Shipping Box Calculator API",
    version="1.0.0",
    description=(
        "Calculate shipping boxes and return each box's package assignments. "
        "Sign in at `/api/v1/auth/token` to receive a JWT before calling "
        "the protected packing endpoint."
    ),
    openapi_tags=[
        {
            "name": "authentication",
            "description": "Sign in and issue short-lived JWT access tokens.",
        }
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
            }
        },
    )

    id: int
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    length: float = Field(gt=0, allow_inf_nan=False)
    weight: float = Field(ge=0, allow_inf_nan=False)


class PackageAssignment(BaseModel):
    id: int
    width: float
    height: float
    length: float
    weight: float


class BoxAssignment(BaseModel):
    box_number: int
    box_type: Literal["A", "B", "C"]
    width: float
    height: float
    length: float
    max_weight: float
    total_weight: float
    packages: list[PackageAssignment]


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
                            },
                            {
                                "id": 125,
                                "width": 5,
                                "height": 5,
                                "length": 10,
                                "weight": 10,
                            },
                        ],
                    }
                ],
            }
        }
    )

    box_count: int
    boxes: list[BoxAssignment]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    is_packing_request = _request.url.path == "/api/v1/pack"
    detail = "Invalid package list." if is_packing_request else "Invalid request."
    errors = exc.errors()
    if _request.url.path == "/api/v1/auth/token":
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
        "weights non-negative. Packages may be rotated. The response includes "
        "each box type and its assigned packages. A package that cannot fit "
        "is reported with HTTP 422."
    ),
    response_description="The box count and package assignments for each box.",
    responses={
        401: {"description": "A valid JWT bearer token is required."},
        422: {
            "description": "Invalid package data or a package that fits no box."
        },
        503: {"description": "JWT signing is not securely configured."},
    },
)
def calculate_boxes(
    packages: list[PackageInput], _user: str = Depends(get_current_user)
) -> PackingResult:
    packing_packages = [
        PackingPackage(
            id=package.id,
            width=package.width,
            height=package.height,
            length=package.length,
            weight=package.weight,
        )
        for package in packages
    ]
    packed_boxes = pack_packages(packing_packages)
    return PackingResult(
        box_count=len(packed_boxes),
        boxes=[_to_box_assignment(box) for box in packed_boxes],
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
            )
            for package in box.packages
        ],
    )
