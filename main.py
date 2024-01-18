import os

import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import docs
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
firebase_app = firebase_admin.initialize_app(
    credential=None,
    options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
)

origins = [
    "https://rocketdocs-frontend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(docs.router)
