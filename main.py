from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import json
import os
from cryptography.fernet import Fernet
import bcrypt

#dot env
from dotenv import load_dotenv
load_dotenv()
FERNET_KEY = os.environ["FERNET_KEY"].encode()


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

# load data file
def load_snippets():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding="utf-8") as f:
            return json.load(f)
    return []

# save snippets to file
def save_snippets(snippets):
    with open(DATA_FILE, 'w', encoding="utf-8") as f:
        json.dump(snippets, f, indent=2)


# initalize snippet list
snippets = load_snippets()

# post route
@app.post('/snippets')
def create_snippet(snippet: Snippet):
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
    save_snippets(snippets)
    return {"message": "Snippet saved successfully", "snippet": snippet_data}

# get all route
@app.get('/snippets')
def get_all_snippets():
    # decrypt the code before returning
    for s in snippets:
        s["code"] = fernet.decrypt(s["code"].encode()).decode()
    return snippets

# get snippet by id
@app.get('/snippets/{snippet_id}')
def get_snippet(snippet_id: int):
    for s in snippets:
        if s["id"] == snippet_id:
            return {
                "id": s["id"],
                "language": s["language"],
                "code": fernet.decrypt(s["code"].encode()).decode()
            }
        
    return {'error': 'Snippets not found'}

# get snippets by language
@app.get('/snippets')
def get_snippet_lang(language: str = None):

    #loop though snippets
    for s in snippets:
        #if language in snippets = language lowercase
        if s["language"].lower() == language.lower():
            #decrypt "code"
            decrypted_code = fernet.decrypt(s["code"].encode()).decode()
            #return values of language
            return {
                "id": s["id"],
                "language": s["language"],
                "code": decrypted_code
            }
