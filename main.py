from fastapi import FastAPI

from routers import hello_world, docs
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.include_router(hello_world.router)
app.include_router(docs.router)
