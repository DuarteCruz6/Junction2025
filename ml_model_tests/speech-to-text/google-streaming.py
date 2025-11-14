import os
import sys
import pyaudio  # Import PyAudio
from dotenv import load_dotenv
from google.api_core.client_options import ClientOptions

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech as cloud_speech_types

script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(script_dir, "..", "..", ".env"))

# --- Configuration ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
if not PROJECT_ID:
    raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set.")

# PyAudio configuration
RATE = 16000
CHUNK = 4096  # 1/4 second of audio data
FORMAT = pyaudio.paInt16
CHANNELS = 1

# --- Generator Functions ---

def microphone_audio_generator():
    """
    A generator function that continuously yields chunks of audio
    data from the microphone.
    """
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK,
    )

    print("🎙️  Start speaking... (Press Ctrl+C to stop)")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            yield data
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        # Clean up the PyAudio stream
        stream.stop_stream()
        stream.close()
        p.terminate()

def request_generator(config_request, audio_generator):
    """
    A generator that yields the initial config request, followed
    by all the audio chunks from the microphone.
    """
    # 1. Send the configuration request first
    yield config_request
    
    # 2. Stream all audio chunks from the microphone generator
    for chunk in audio_generator:
        yield cloud_speech_types.StreamingRecognizeRequest(audio=chunk)

# --- Main Transcription Function ---

def transcribe_streaming_live():
    """
    Transcribes live audio from the microphone using
    Google Cloud Speech-to-Text V2.
    """
    # Define your region and regional endpoint
    LOCATION = "us-central1"
    API_ENDPOINT = f"{LOCATION}-speech.googleapis.com"

    # Pass the endpoint to the client
    client_options = ClientOptions(api_endpoint=API_ENDPOINT)
    client = SpeechClient(client_options=client_options)

    # 1. Define the recognition config
    recognition_config = cloud_speech_types.RecognitionConfig(
        auto_decoding_config=cloud_speech_types.AutoDetectDecodingConfig(),
        language_codes=["en-US"],
        model="chirp",  # Use the "chirp" model
    )

    # 2. Define the streaming config
    #    enable_automatic_punctuation=True,
    streaming_config = cloud_speech_types.StreamingRecognitionConfig(
        config=recognition_config,
    )

    # 3. Define the initial config request
    config_request = cloud_speech_types.StreamingRecognizeRequest(
        recognizer=f"projects/{PROJECT_ID}/locations/{LOCATION}/recognizers/_",
        streaming_config=streaming_config,
    )

    # 4. Create the generators
    audio_gen = microphone_audio_generator()
    requests = request_generator(config_request, audio_gen)

    # 5. Make the streaming recognize request
    try:
        responses_iterator = client.streaming_recognize(requests=requests)

        print("-" * 20)
        
        # 6. Loop over the responses
        for response in responses_iterator:
            print(f"DEBUG: Received response object: {response}") # <-- ADD THIS LINE
            for result in response.results:
                if not result.alternatives:  # Check if the list is empty
                    continue  # Skip this result if there are no alternatives

                transcript = result.alternatives[0].transcript
                
                if result.is_final:
                
                    # Clear the line and print the final transcript
                    sys.stdout.write("\r" + " " * 80 + "\r")
                    print(f"✅ Final:    {transcript}\n")
                else:
                    # Print the interim transcript, overwriting the previous one
                    sys.stdout.write(f"\r💬 Interim: {transcript}")
                    sys.stdout.flush()

    except Exception as e:
        if "idle" in str(e) or "exceeded" in str(e):
            print("\nStream timed out. This is normal.")
        else:
            print(f"\nAn error occurred: {e}")

if __name__ == "__main__":
    transcribe_streaming_live()