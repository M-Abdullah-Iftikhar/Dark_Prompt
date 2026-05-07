# Dark Prompt

LLM-driven malware generation frontend for proactive AV research. Django web app
that talks to a locally hosted Flask LLM endpoint.

## Setup

```bash
# 1. Create and activate a virtualenv (Python 3.11+)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply migrations
python manage.py migrate

# 4. (Optional) Create a superuser
python manage.py createsuperuser

# 5. Run the dev server
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

## LLM backend

The chat view forwards prompts to the Flask endpoint configured in
`darkprompt/settings.py` as `LLM_API_URL` (default
`http://127.0.0.1:5000/generate`). Override with the `LLM_API_URL` environment
variable if needed.

The expected request/response shape:

```http
POST /generate
Content-Type: application/json

{
  "instruction": "<user prompt>",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

```json
{ "response": "<generated code as string>" }
```

## Project layout

```
darkprompt/        # project settings + root urls
core/              # public landing page
accounts/          # signup / login / logout
chat/              # conversation models + chat UI + /api/chat/
templates/         # base.html and per-app templates
static/            # css + js
```
