from fastapi import FastAPI

from routers import docs
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.include_router(docs.router)
