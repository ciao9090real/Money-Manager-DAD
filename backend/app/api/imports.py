from fastapi import APIRouter, HTTPException


router = APIRouter()


@router.api_route("/imports/{path:path}", methods=["GET", "POST", "PATCH", "DELETE"])
def imports_disabled(path: str):
    raise HTTPException(status_code=410, detail="Statement imports are disabled while the workflow is redesigned.")
