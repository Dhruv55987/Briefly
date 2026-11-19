import os
from dotenv import load_dotenv

load_dotenv()
from utils.audio_processor import process_input
from core.transcriber import transcribe_all
from core.summarize import summarize, generate_title
from core.extractor import extract_action_items, extract_key_decisions, extract_questions
from core.rag_engine import build_rag_chain, ask_question
from core.youtube_transcript import fetch_youtube_transcript, is_youtube_url


def run_pipeline(source: str, language: str = "english", progress_callback=None) -> dict:
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError(
            "Missing GROQ_API_KEY. Add GROQ_API_KEY=<your Groq API key> to your .env file. "
        )
    def report(message: str, percent: int) -> None:
        print(message)
        if progress_callback:
            progress_callback(message, percent)

    if is_youtube_url(source):
        report("Retrieving YouTube captions", 28)
        transcript = fetch_youtube_transcript(source)
    else:
        report("Preparing audio", 8)
        chunks = process_input(source)
        report(f"Transcribing audio ({len(chunks)} chunk(s))", 28)
        transcript = transcribe_all(chunks, language)

    report("Generating title and summary", 55)
    title = generate_title(transcript)

    summary = summarize(transcript)

    report("Extracting action items and decisions", 76)
    action_item = extract_action_items(transcript)

    decisions = extract_key_decisions(transcript)
    questions = extract_questions(transcript)
    
    report("Preparing transcript chat", 93)
    rag_chain = build_rag_chain(transcript)

    return {
        "title": title,
        "transcript": transcript,
        "summary": summary,
        "action_items": action_item,
        "key_decisions": decisions,
        "open_questions": questions,
        "rag_chain": rag_chain,
    }

if __name__ == "__main__":
    # CLI entry point
    source = input("Enter YouTube URL or local file path: ").strip()
    language = input("Language (english/hinglish): ").strip() or "english"
    result = run_pipeline(source, language)

    print("\n" + "=" * 60)
    print(f"📌 Title: {result['title']}")
    print(f"\n📋 Summary:\n{result['summary']}")
    print(f"\n✅ Action Items:\n{result['action_items']}")
    print(f"\n🔑 Key Decisions:\n{result['key_decisions']}")
    print(f"\n❓ Open Questions:\n{result['open_questions']}")
    print("=" * 60)

    # Phase 2 — Chat with your meeting via RAG
    print("\n💬 Chat with your meeting (type 'exit' to quit)\n")
    rag_chain = result["rag_chain"]
    while True:
        question = input("You: ").strip()
        if question.lower() in ["exit", "quit", "q"]:
            print("👋 Goodbye!")
            break
        if not question:
            continue
        answer = ask_question(rag_chain, question)
        print(f"\n🤖 Assistant: {answer}\n")
