import os

import firebase_admin
from fastapi import FastAPI

from routers import docs
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
firebase_app = firebase_admin.initialize_app(
    credential=None,
    options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
)

app.include_router(docs.router)
