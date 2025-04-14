from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import difflib

app = FastAPI(title="Illegal Dumping Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

# Load questions from JSON
with open("qa_data.json", "r", encoding="utf-8") as f:
    qa_data = json.load(f)

class ChatRequest(BaseModel):
    message: str

friendly_responses = {
    "hi": "Hello! How can I help you today?",
    "hello": "Hi there! Ask me anything about waste management or illegal dumping.",
    "hey": "Hey! What would you like to know?",
    "thanks": "You're welcome! 😊",
    "thank you": "Happy to help!",
    "bye": "Goodbye! Stay clean and green!",
    "goodbye": "Take care!",
    "see you": "Catch you later!",
    "how are you": "I'm just a chatbot, but I'm functioning great! How can I help you today?",
    "who are you": "I'm DumpBot, your assistant for illegal dumping and community waste questions.",
    "what can you do": "I can answer questions about illegal dumping, waste services, community clean-ups, and more!"
}

# Normalize message
def normalize(text):
    return text.lower().strip()

# Fuzzy match function
def find_best_answer(user_input: str) -> str:
    # Check for greetings, thanks, etc.
    normalized = normalize(user_input)
    if normalized in friendly_responses:
        return friendly_responses[normalized]

    # Fuzzy match with questions
    questions = [item["question"] for item in qa_data]
    match = difflib.get_close_matches(user_input, questions, n=1, cutoff=0.5)
    if match:
        for item in qa_data:
            if item["question"] == match[0]:
                return item["answer"]
    
    return "Sorry, I couldn't find an answer to that. Please try rephrasing your question."

# API endpoint
@app.post("/ask")
def ask_question(request: ChatRequest):
    answer = find_best_answer(request.message)
    return {"answer": answer}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Illegal Dumping Chatbot API"}

# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "Illegal Dumping Chatbot"}