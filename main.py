import os
import ssl

import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import docs, repos
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# SSL certificates for HTTPS
if os.getenv("ENV") == "prod":
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain("./creds/fullchain.pem", "./creds/privkey.pem")

# Cross-Origin requests
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

# Include Routers
app.include_router(docs.router)
app.include_router(repos.router)

# Initializing Firebase App
firebase_app = firebase_admin.initialize_app(
    credential=None,
    options={"storageBucket": os.getenv("CLOUD_STORAGE_BUCKET")}
)
