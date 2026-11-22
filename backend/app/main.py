from fastapi import Depends, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.auth import get_current_user, router as auth_router
from app.packing import Package as PackingPackage
from app.packing import UnpackablePackageError, pack_packages

app = FastAPI(
    title="Shipping Box Calculator API",
    version="1.0.0",
    description=(
        "Calculate the number of shipping boxes for a package list. "
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


class PackingResult(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"box_count": 1}})

    box_count: int


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
    summary="Calculate the required box count",
    description=(
        "Accept a JSON array of packages. Dimensions must be positive and "
        "weights non-negative. Packages may be rotated. A package that cannot "
        "fit is reported with HTTP 422."
    ),
    response_description="The number of shipping boxes required.",
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
    return PackingResult(box_count=pack_packages(packing_packages))
