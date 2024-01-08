# rocketdocs

### Usage
If it's your first time, check out the "First Time Install" guide below.

#### Running API on dev mode
Use `uvicorn main:app --reload`. A server will open on `http://127.0.0.1:8000`

FastAPI provides the following tools:
- `http://127.0.0.1:8000/docs`: an interactive API documentation (provided by Swagger UI).
- `http://127.0.0.1:8000/redoc`: an alternative automatic documentation (provided by ReDoc).

#### Running individual python files
Use `python -m {module path}`. For example `python -m services.hello_world`.

### First Time Install
For best experience use Python version `3.10.13`.

1. run `pip install -r requirements.txt`