from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from utils.file_operations import RequestContext, endpoints
from fs import errors
from utils.auth import oauth2_scheme, get_current_user

router = APIRouter()

# @router.api_route("/{username}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
# async def dispatch_request(request: Request, username: str, token: str = Depends(oauth2_scheme)):

@router.api_route("/{username}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def dispatch_request(request: Request, username: str):
    headers = {}
    if request.method == "OPTIONS":
        return JSONResponse(headers=headers)

    q = request.query_params.get("q")
    if q not in ["preview", "download"]:
        # 验证用户
        token = await oauth2_scheme(request)
        user = await get_current_user(request)

    if not q or q not in endpoints:
        raise HTTPException(status_code=400, detail="Invalid endpoint")

    try:
        response = await endpoints[q](RequestContext(request, username))
    except errors.ResourceReadOnly as exc:
        return JSONResponse({"message": str(exc), "status": False}, status_code=400)
    except HTTPException as exc:
        return JSONResponse({"message": exc.detail, "status": False}, status_code=exc.status_code)
    except Exception as exc:
        return JSONResponse({"message": str(exc), "status": False}, status_code=500)    

    return response 