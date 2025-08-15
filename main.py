from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from pydantic import BaseModel
import os
import json
import bcrypt
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken


# dot env
from dotenv import load_dotenv
load_dotenv()

# FERNET_KEY = os.environ["FERNET_KEY"].encode()
# fernet_key = Fernet.generate_key()
# print("Generated Fernet Key:", fernet_key.decode())


# cryptography key for encryption/decryption
# fernet = Fernet(FERNET_KEY)

# create fastAPI instance
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET", "!supersecret"))

# OAuth Config
config = Config('.env')
oauth = OAuth(config)
oauth.register(
    name='auth0',
    client_id=os.getenv("AUTH0_CLIENT_ID"),
    client_secret=os.getenv("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        'scope': 'openid profile email'
    },
    server_metadata_url=f"https://{os.getenv('AUTH0_DOMAIN')}/.well-known/openid-configuration"
)

# dependency function
def require_login(request: Request):
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# data file
DATA_FILE = "seedData.json"

# pydantic model for snippet - defines what a user must send when creating a snippet
class Snippet(BaseModel):
    language: str
    code: str

class User(BaseModel):
    email: str
    password: str

# load data file
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    return {"snippets": [], "users": []}

# save snippets to file
def save_data(data):
    with open(DATA_FILE, 'w', encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# initalize snippet list
data = load_data()
snippets = data["snippets"]
users = data["users"]


AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
REDIRECT_AFTER_LOGOUT = "http://127.0.0.1:8000/"

# auth login
@app.get("/login")
async def login(request: Request):
    redirect_uri = request.url_for("callback")
    return await oauth.auth0.authorize_redirect(request, redirect_uri)


@app.get("/callback")
async def callback(request: Request):
    token = await oauth.auth0.authorize_access_token(request)
    print("TOKEN", token)

    # ✅ Just use token["userinfo"]
    user_info = token.get("userinfo")
    print("USERINFO:", user_info)

    request.session["user"] = dict(user_info)
    return RedirectResponse(url="/snippets")

@app.get("/logout")
async def logout(request: Request):

    request.session.clear()

    logout_url = (
        f"https://{AUTH0_DOMAIN}/v2/logout"
        f"?client_id={AUTH0_CLIENT_ID}"
        f"&returnTo={REDIRECT_AFTER_LOGOUT}"
    )
    return RedirectResponse(url=logout_url)

# post route
@app.post('/snippets')
def create_snippet(snippet: Snippet, user: dict = Depends(require_login)):
    # gets max id from existing snippets or starts at 1 and increments it
    snippet_id = max([s['id'] for s in snippets], default=0) + 1

    # encrypt the code before saving
    # encrypted_code = fernet.encrypt(snippet.code.encode()).decode()

    # create a new snippet with the encrypted code
    snippet_data = {
        "id": snippet_id,
        "language": snippet.language,
        "code": snippet.code
    }

    # append data to snippets list and save to file
    snippets.append(snippet_data)
    save_data({
        "snippets": snippets,
        "users": users
    })
    return {"message": "Snippet saved successfully", "snippet": snippet_data}

# get all route
@app.get('/snippets')
def get_all_snippets(user: dict = Depends(require_login)):
    # decrypt the code before returning
    # for s in snippets:
    #     s["code"] = fernet.decrypt(s["code"].encode()).decode()
    return snippets


# get snippets by language
@app.get('/snippets/language')
def get_snippet_lang(language: str = None, user: dict = Depends(require_login)):
    result = []

    if not language:
        return []

    # loop though snippets
    for s in snippets:
        # if language in snippets = language lowercase
        if s["language"].lower() == language.lower():
            # try:
            #     # decrypt "code"
            #     decrypted_code = fernet.decrypt(s["code"].encode()).decode()
            # except InvalidToken:
            #     decrypted_code = "<decryption failed: invalid token>"
            # return values of language
            result.append({
                "id": s["id"],
                "language": s["language"],
                "code": s["code"]
            })

    return result


# get snippet by id
@app.get('/snippets/{snippet_id}')
def get_snippet(snippet_id: int, user: dict = Depends(require_login)):
    for s in snippets:
        if s["id"] == snippet_id:
            # try:
            #     decrypted_code = fernet.decrypt(s["code"].encode()).decode()
            # except InvalidToken:
            #     return {
            #         "id": s["id"],
            #         "language": s["language"],
            #         "code": "<decryption failed: invalid token>"
            #     }

            return {
                "id": s["id"],
                "language": s["language"],
                "code": s["code"]
            }

    return {'error': 'Snippets not found'}

# not used anymore becuase of auth0?
@app.post('/user')
def create_user(user: User):
    # hash the password
    hashed_password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())

    # save user to file and append to snippets and save to seedData.json
    user_data = {
        "email": user.email,
        "password": hashed_password.decode()
    }
    users.append(user_data)
    save_data({
        "snippets": snippets,
        "users": users
    })

    return {"message": "User created successfully", "user": user_data}
