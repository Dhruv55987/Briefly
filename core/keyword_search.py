"""Small, per-transcript text retriever for memory-constrained deployments."""
import re
from collections import Counter
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda
from langchain_text_splitters import RecursiveCharacterTextSplitter


def build_retriever(transcript: str, k: int = 4):
    chunks = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=150
    ).split_text(transcript)
    documents = [Document(page_content=text) for text in chunks]
    tokens = [Counter(re.findall(r"\w+", text.lower())) for text in chunks]

    def retrieve(question: str):
        terms = set(re.findall(r"\w+", question.lower()))
        ranked = sorted(
            range(len(documents)),
            key=lambda i: sum(tokens[i][term] for term in terms),
            reverse=True,
        )[:k]
        return [documents[i] for i in ranked]

    return RunnableLambda(retrieve)
