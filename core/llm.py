"""Shared configuration for hosted text generation."""
import os

from langchain_groq import ChatGroq


def get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GROQ_API_KEY. Set it in .env or your host's environment settings.")
    return ChatGroq(model="openai/gpt-oss-120b", temperature=0.3, groq_api_key=api_key)
