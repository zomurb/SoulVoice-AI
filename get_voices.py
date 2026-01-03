import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

if not ELEVENLABS_API_KEY:
    print("❌ Error: ELEVENLABS_API_KEY not found in .env")
    exit(1)

client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

print("Fetching available voices from ElevenLabs...\n")
try:
    response = client.voices.get_all()
    # verify structure, response might be an object with .voices or a list
    voices = response.voices if hasattr(response, 'voices') else response

    print(f"{'NAME':<20} | {'CATEGORY':<15} | {'ID'}")
    print("-" * 70)
    for voice in voices:
        print(f"{voice.name:<20} | {voice.category:<15} | {voice.voice_id}")
        
    print("\n✅ Copy the ID of the voice you like and paste it into bot.py in the VOICE_OPTIONS dictionary.")

except Exception as e:
    print(f"Error fetching voices: {e}")
