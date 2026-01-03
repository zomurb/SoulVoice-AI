import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()
client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

response = client.voices.get_all()
voices = response.voices if hasattr(response, 'voices') else response

if voices:
    v = voices[0]
    print(f"Name: {v.name}")
    print(f"Preview URL: {getattr(v, 'preview_url', 'N/A')}")
    print(f"All vars: {vars(v)}")
else:
    print("No voices found")
