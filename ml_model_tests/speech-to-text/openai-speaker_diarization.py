import base64
from openai import OpenAI
import os
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "meeting-pt.m4a")

load_dotenv(dotenv_path=os.path.join(script_dir, "..", "..", ".env"))

client = OpenAI(
  api_key=os.getenv("OPENAI_API_KEY"),
)


def to_data_url(path: str) -> str:
    with open(path, "rb") as fh:
        return "data:audio/wav;base64," + base64.b64encode(fh.read()).decode("utf-8")
    
with open(file_path, "rb") as audio_file:
    transcript = client.audio.transcriptions.create(
        model="gpt-4o-transcribe-diarize",
        file=audio_file,
        response_format="diarized_json",
        chunking_strategy="auto",
        extra_body={
            "known_speaker_names": ["dudu","andre","daniel"],
            "known_speaker_references": [
                                         to_data_url(os.path.join(script_dir, "dudu.m4a")),
                                         to_data_url(os.path.join(script_dir, "andre.m4a")),
                                         to_data_url(os.path.join(script_dir, "daniel.m4a"))
                                        ],
        },
    )

for segment in transcript.segments:
    print(segment.speaker, segment.text, segment.start, segment.end)