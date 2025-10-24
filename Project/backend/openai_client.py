import openai
import os
import requests
import json
import re

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "ollama")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen:1.8b")

openai.api_key = OPENAI_API_KEY
openai.api_base = OPENAI_API_BASE

def clean_ascii(text):
    if text is None:
        return ""
    return text.encode("ascii", "ignore").decode()

def validate_question(response, system_prompt):
    """Validate that response is a proper question following the prompt"""
    response = response.strip()
    
    intended_question = ""
    match = re.search(r'QUESTION TO ASK: "(.+?)"', system_prompt)
    if match:
        intended_question = match.group(1)
    
    if intended_question and intended_question not in response:
        return intended_question
    
    if not response.endswith('?'):
        response = response + '?'
    
    return response

def chat_with_gpt(messages, model=None, temperature=0.1, max_tokens=80):
    """
    Professional AI that follows strict conversation rules
    """
    if model is None:
        model = DEFAULT_MODEL
        
    cleaned = [{"role": m["role"], "content": clean_ascii(m["content"])} for m in messages]

    try:
        system_prompt = ""
        for msg in cleaned:
            if msg["role"] == "system":
                system_prompt = msg["content"]
                break
        
        resp = openai.ChatCompletion.create(
            model=model, 
            messages=cleaned, 
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=10
        )
        response = resp.choices[0].message["content"].strip()
        
        validated_response = validate_question(response, system_prompt)
        
        return validated_response
        
    except Exception as e:
        print(f"AI service error: {e}")
        for msg in messages:
            if msg["role"] == "system":
                match = re.search(r'QUESTION TO ASK: "(.+?)"', msg["content"])
                if match:
                    return match.group(1)
        return "Can you provide more details about this?"