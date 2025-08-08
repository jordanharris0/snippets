from fastapi import FastAPI, Depends, Header, HTTPException, status
from datetime import datetime, timedelta, timezone
import base64
from pydantic import BaseModel
from typing import Optional
import json
import os
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
import bcrypt
import jwt

#dot env
from dotenv import load_dotenv
load_dotenv()
FERNET_KEY = os.environ["FERNET_KEY"].encode()
JWT_SECRET = os.getenv("JWT_SECRET", "secret")
JWT_ALGORITHM = "HS256"
TOKEN_EXPIRES = 24


#cryptography key for encryption/decryption
fernet = Fernet(FERNET_KEY) 

# create fastAPI instance
app = FastAPI()

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

# auth helper functions

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=TOKEN_EXPIRES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def parse_basic_auth_header(auth_header: str | None):
    if not auth_header or not auth_header.startswith("Basic "):
        return None, None
    try:
        b64 = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(b64).decode("utf-8")
        email, password = decoded.split(":", 1)
        return email, password
    except Exception:
        return None, None
    
def require_jwt_token(Authorization: str | None = Header(default=None)):
    if not Authorization or not Authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Bearer token")
    
    token = Authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

# initalize snippet list
data = load_data()
snippets = data["snippets"]
users = data["users"]

# post route
@app.post('/snippets')
def create_snippet(snippet: Snippet, _user: dict = Depends(require_jwt_token)):
    # gets max id from existing snippets or starts at 1 and increments it
    snippet_id = max([s['id'] for s in snippets], default=0) + 1

    # encrypt the code before saving
    encrypted_code = fernet.encrypt(snippet.code.encode()).decode()

    # create a new snippet with the encrypted code
    snippet_data = {
        "id": snippet_id,
        "language": snippet.language,
        "code": encrypted_code
    }

    #append data to snippets list and save to file
    snippets.append(snippet_data)
    save_data({
    "snippets": snippets,
    "users": users
    })
    return {"message": "Snippet saved successfully", "snippet": snippet_data}

# get all route
@app.get('/snippets')
def get_all_snippets():
    # decrypt the code before returning
    for s in snippets:
        s["code"] = fernet.decrypt(s["code"].encode()).decode()
    return snippets


# get snippets by language
@app.get('/snippets/language')
def get_snippet_lang(language: str = None):
    result = []

    if not language:
        return []

    #loop though snippets
    for s in snippets:
        #if language in snippets = language lowercase
        if s["language"].lower() == language.lower():
            try:
                #decrypt "code"
                decrypted_code = fernet.decrypt(s["code"].encode()).decode()
            except InvalidToken:
                decrypted_code = "<decryption failed: invalid token>"
            #return values of language
            result.append( {
                "id": s["id"],
                "language": s["language"],
                "code": decrypted_code
            })

    return result


# get snippet by id
@app.get('/snippets/{snippet_id}')
def get_snippet(snippet_id: int):
    for s in snippets:
        if s["id"] == snippet_id:
            try:
                decrypted_code = fernet.decrypt(s["code"].encode()).decode()
            except InvalidToken:
                return {
                    "id": s["id"],
                    "language": s["language"],
                    "code": "<decryption failed: invalid token>"
                }
                
            return {
                "id": s["id"],
                "language": s["language"],
                "code": decrypted_code
            }
        
    return {'error': 'Snippets not found'}



@app.post('/user')
def create_user(user: User):
    #hash the password
    hashed_password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())

    #save user to file and append to snippets and save to seedData.json
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
            
# login route
@app.post('/auth/login')
def login(Authorization: str | None = Header(default=None)):
    email, password = parse_basic_auth_header(Authorization)
    if not email or not password:
        raise HTTPException(401, "Invalid Basic auth header")
    
    user = next((u for u in users if u["email"].lower() == email.lower()), None)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    
    if not bcrypt.checkpw(password.encode(), user["password"].encode()):
        raise HTTPException(401, "Invalid email or password")
    
    token = create_access_token({"sub": email})
    return {"access_token": token, "token_type": "bearer", "expires_in": 24*3600}
