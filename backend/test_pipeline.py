import os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://dummy:dummy@localhost:5432/dummy'
os.environ['SUPABASE_URL'] = 'https://dummy.supabase.co'
os.environ['SUPABASE_ANON_KEY'] = 'dummy'
os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'dummy'
os.environ['SUPABASE_JWT_SECRET'] = 'dummy'
os.environ['OPENAI_API_KEY'] = 'dummy'
os.environ['GEMINI_API_KEY'] = 'dummy'
import asyncio
from pathlib import Path
from app.workers.tasks import _transcribe_with_faster_whisper, _generate_gemini_summary, get_whisper_model
import json

def test_file(filepath: Path):
    print(f"=== Testing {filepath.name} ===")
    
    raw_text, segments, duration = _transcribe_with_faster_whisper(filepath)
    print(f"Transcript ({len(raw_text)} chars): '{raw_text}'")
    print(f"Duration: {duration} seconds")
    
    if len(raw_text.strip()) < 50:
        print("Transcript is empty or below minimum character threshold. Skipping summarization.")
        summary_data = {
            "executive_summary": "No speech detected in the uploaded audio.",
            "key_takeaways": [],
            "action_items": []
        }
    else:
        print("Transcript long enough, running summarization...")
        summary_data = _generate_gemini_summary(raw_text)
        
    print(f"Summary Output:\n{json.dumps(summary_data, indent=2)}\n")

if __name__ == "__main__":
    import os
    os.environ['KMP_DUPLICATE_LIB_OK']='True'
    # Warm up model
    get_whisper_model()
    
    test_file(Path('../silent.wav'))
    test_file(Path('../spoken.wav'))
