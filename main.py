from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import json
import os

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
    snippet_id = max([s['id'] for s in snippets], default=0) + 1
    snippet_data = {
        "id": snippet_id,
        **snippet.model_dump()
    }
    snippets.append(snippet_data)
    save_snippets(snippets)
    return snippet_data

# get all route


@app.get('/snippets')
def get_all_snippets(lang: Optional[str] = None):
    if lang:
        return [s for s in snippets if s["language"].lower() == lang.lower()]
    return snippets

# get snippet by id


@app.get('/snippets/{snippet_id}')
def get_snippet(snippet_id: int):
    for s in snippets:
        if s["id"] == snippet_id:
            return s
    return {'error': 'Snippets not found'}


@app.get('/snippets')
def get_snippet_lang(language: str = None):
    if language:
        return [s for s in snippets if s["language"].lower() == language.lower()]
    return snippets
