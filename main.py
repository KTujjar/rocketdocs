from fastapi import FastAPI

from routers import hello_world
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.include_router(hello_world.router)
