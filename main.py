from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from http import HTTPStatus
import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path='key.env')   # load API key from .env file


app = FastAPI()

# 1. Allow the frontend to talk with this backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],   # In production, change this to your vercel URL.
    allow_credentials = True,
    allow_methods = ["*"],
    allow_headers = ["*"],
)

# 2. Define the data we expact from the frontend.
class PromptRequest(BaseModel):
    prompt: str


# 3. The list of models (Using free ones from openrouter)
MODELS = [
    "x-ai/grok-4.1-fast:free",
    "google/gemini-2.0-flash-exp:free", # Added Gemini (usually reliable)
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-7b-instruct:free",
    "mistralai/mistral-nemo:free",
    
]

OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")


# --- TRAFFIC CONTROL ---
# This limits us to 2 parallel requests at a time to avoid 429 Errors ## It was my first try... failed
# Set to 1 to be extremely safe with free tier limits ## 2nd try...
MAX_CONCURRENT_REQUESTS = 1

#. Helper function to call one model
async def fetch_model_response(client, model, prompt):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPEN_ROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173", # OpenRouter often requires these for free tier
        "X-Title": "LLM Council",
    }

    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = await client.post(url, headers=headers, json=data, timeout=45.0)

        # If we get a 429 (Rate Limit), we wait 2 seconds and try ONE more time
        if response.status_code == 429:
            await asyncio.sleep(2)
            response = await client.post(url, headers=headers, json=data, timeout=45.0)

        response.raise_for_status()
        result = response.json()
        return {
            "model": model,
            "answer": result['choices'][0]['message']['content']
        }
    
    except httpx.HTTPStatusError as e:
        # If OpenRouter returns 401, 403, 429, etc.
        return {"model": model, "answer": f"HTTP Error {e.response.status_code}. Key/Quota issue."}

    # For network timeouts, JSON decode issues, etc.
    except Exception as e:
        return {"model": model, "answer": f"Error: {str(e)}"}


async def get_council_decision(client, prompt, model_responses):
    """The Judge Model evaluates the answers."""
    judge_model = "x-ai/grok-4.1-fast:free" # A smart, fast model
    
    # Filter out failed models before sending to judge
    valid_responses = [m for m in model_responses if "Error" not in m['answer']]

    if not valid_responses:
        return "The Council failed to retrieve valid answers to judge."

    # --- SAFETY PAUSE ---
    # Wait 3 seconds before asking the judge to let the API cooldown
    await asyncio.sleep(3) 
    # --------------------

    # Create a summary context for the judge
    context = f"User Question: {prompt}\n\n"
    for item in model_responses:
        context += f"Model {item['model']} said:\n{item['answer']}\n\n"
    
    context += "You are the Head Councilor. Analyze the answers above. 1. Pick the best answer. 2. Explain why. 3. Synthesize the final perfect answer for the user."

    # Re-use the fetch logic (simplified for the judge)
    try:
        decision = await fetch_model_response(client, judge_model, context)
        return decision['answer']
    except Exception as e:
        return f"The High Council could not reach a verdict. (Error: {str(e)})"
    



# 5. The API endpoint

@app.post("/ask-council")
async def ask_council(request: PromptRequest):
    async with httpx.AsyncClient() as client:

        # Create a Semaphore to limit concurrency
        sem = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def controlled_fetch(model):
            async with sem: # Wait here if 2 requests are already active
                return await fetch_model_response(client, model, request.prompt)

        # 1. Ask all council members (Controlled speed)
        tasks = [controlled_fetch(model) for model in MODELS]
        results = await asyncio.gather(*tasks)
        
        # 2. Ask the Judge to evaluate (Wait for members to finish first)
        verdict = await get_council_decision(client, request.prompt, results)
        
    # Return both the individual answers AND the final verdict
    return {
        "individual_responses": results,
        "council_verdict": verdict
    }