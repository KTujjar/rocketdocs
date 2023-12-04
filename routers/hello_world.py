from fastapi import APIRouter, Depends

from schemas.hello_world import HelloWorldResponse
from services.hello_world import HelloWorldService, get_hello_world_service

router = APIRouter()


@router.get("/ping")
def ping() -> str:
    return "pong"


@router.get("/hello_world")
def hello_world(
        hello_world_service: HelloWorldService = Depends(get_hello_world_service)
) -> HelloWorldResponse:
    data = hello_world_service.say_hello_world()
    return data
