import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from app.packing import Package as PackingPackage
from app.packing import UnpackablePackageError, pack_packages

app = FastAPI(title="Shipping Box Calculator", version="1.0.0")
bearer_scheme = HTTPBearer(auto_error=False)


def require_api_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    expected_token = os.getenv("API_AUTH_TOKEN")
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="API authentication is not configured.",
        )

    provided_token = credentials.credentials if credentials is not None else ""
    valid_token = credentials is not None and credentials.scheme.lower() == "bearer"
    valid_token = valid_token and secrets.compare_digest(
        provided_token.encode("utf-8"),
        expected_token.encode("utf-8"),
    )
    if not valid_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PackageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    width: float = Field(gt=0, allow_inf_nan=False)
    height: float = Field(gt=0, allow_inf_nan=False)
    length: float = Field(gt=0, allow_inf_nan=False)
    weight: float = Field(ge=0, allow_inf_nan=False)


class PackingResult(BaseModel):
    box_count: int


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid package list.",
            "errors": jsonable_encoder(exc.errors()),
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
    dependencies=[Depends(require_api_token)],
)
def calculate_boxes(packages: list[PackageInput]) -> PackingResult:
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
