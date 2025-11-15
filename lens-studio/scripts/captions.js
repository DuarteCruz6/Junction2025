/**
 * Captions Script
 * Displays real-time speech-to-text captions and translations
 * Updates as audio is processed by the backend
 */

// @input Component.ScriptComponent apiClientScript
// @input Component.AudioComponent audioComponent

// Get captions entity safely (if needed)
// const captions = (script.apiContext && script.apiContext.entity) ? script.apiContext.entity : null;

// Caption display elements
let captionText = null;
let translationText = null;
let isEnabled = false;

// Caption state
let currentCaption = "";
let currentTranslation = "";
let captionHistory = [];

// Audio processing
let audioStream = null;
let audioUpdateInterval = null;
let microphoneAudioProvider = null;
let audioBuffer = [];
let vadState = {
    isSpeech: false,
    silenceDuration: 0,
    speechDuration: 0,
    energyThreshold: 0.01, // Adjust based on testing
    minSilenceDuration: 0.3, // 300ms of silence to end chunk (reduced for faster response)
    minSpeechDuration: 0.15, // 150ms of speech to start chunk (reduced for faster detection)
    maxChunkDuration: 1.5, // Max 1.5 seconds before forcing chunk (reduced for lower latency)
    sampleRate: 16000,
    chunkSize: 1600 // ~100ms at 16kHz (16000 * 0.1 * 1 channel * 2 bytes)
};

function initialize() {
    print("Captions: Initializing...");
    
    // Create caption display elements
    createCaptionDisplay();
    
    print("Captions: Initialized");
}

function createCaptionDisplay() {
    // Create text components for captions and translations
    // This will be configured in Lens Studio scene
    
    print("Captions: Caption display created");
}

function startAudioCapture() {
    try {
        // Get MicrophoneAudioProvider from the audio component
        if (script.audioComponent) {
            microphoneAudioProvider = script.audioComponent.getComponent("MicrophoneAudioProvider");
        }
        
        if (!microphoneAudioProvider) {
            // Try to get it from the scene
            const scene = script.getScene();
            const audioComponent = scene.getComponent("AudioComponent");
            if (audioComponent) {
                microphoneAudioProvider = audioComponent.getComponent("MicrophoneAudioProvider");
            }
        }
        
        if (!microphoneAudioProvider) {
            print("Captions: MicrophoneAudioProvider not found. Please add it to your scene.");
            return;
        }
        
        // Enable microphone
        microphoneAudioProvider.enabled = true;
        
        // Start capturing audio
        audioUpdateInterval = script.createEvent("UpdateEvent");
        audioUpdateInterval.bind(function() {
            if (isEnabled && script.apiClient.isRecording) {
                captureAndProcessAudio();
            }
        });
        
        // Set up transcription callback
        script.apiClient.onTranscriptionResult = function(data) {
            if (data.segments && data.segments.length > 0) {
                data.segments.forEach(function(segment) {
                    updateCaption(segment.text, segment.speaker);
                });
            }
        };
        
        print("Captions: Audio capture started");
    } catch (error) {
        print(`Captions: Error starting audio capture: ${error.message}`);
    }
}

function calculateAudioEnergy(audioData) {
    // Calculate RMS (Root Mean Square) energy
    let sumSquares = 0;
    const samples = new Int16Array(audioData);
    
    for (let i = 0; i < samples.length; i++) {
        const sample = samples[i] / 32768.0; // Normalize to -1.0 to 1.0
        sumSquares += sample * sample;
    }
    
    return Math.sqrt(sumSquares / samples.length);
}

function captureAndProcessAudio() {
    if (!microphoneAudioProvider || !isEnabled || !script.apiClient.isRecording) {
        return;
    }
    
    try {
        // Get audio data from microphone
        // MicrophoneAudioProvider provides audio samples
        const audioData = microphoneAudioProvider.getAudioBuffer();
        
        if (!audioData || audioData.length === 0) {
            return;
        }
        
        // Convert to PCM format if needed
        // Assuming audioData is already in the right format (Int16Array or similar)
        let pcmData;
        if (audioData instanceof Int16Array) {
            pcmData = audioData.buffer;
        } else if (audioData instanceof ArrayBuffer) {
            pcmData = audioData;
        } else {
            // Convert to ArrayBuffer
            pcmData = new Int16Array(audioData).buffer;
        }
        
        // Calculate audio energy for VAD
        const energy = calculateAudioEnergy(pcmData);
        const isSpeechDetected = energy > vadState.energyThreshold;
        
        // VAD State Machine
        if (isSpeechDetected) {
            vadState.speechDuration += vadState.chunkSize / vadState.sampleRate;
            vadState.silenceDuration = 0;
            
            if (!vadState.isSpeech && vadState.speechDuration >= vadState.minSpeechDuration) {
                vadState.isSpeech = true;
            }
        } else {
            vadState.silenceDuration += vadState.chunkSize / vadState.sampleRate;
            vadState.speechDuration = 0;
            
            if (vadState.isSpeech && vadState.silenceDuration >= vadState.minSilenceDuration) {
                // End of speech - send chunk
                sendAudioChunk(true);
                vadState.isSpeech = false;
                vadState.silenceDuration = 0;
                return;
            }
        }
        
        // Add to buffer
        audioBuffer.push(pcmData);
        
        // Calculate total buffer duration
        const bufferDuration = (audioBuffer.length * vadState.chunkSize) / vadState.sampleRate;
        
        // Send chunk if:
        // 1. We have speech and buffer is getting long
        // 2. Max duration reached (force send)
        if (vadState.isSpeech && bufferDuration >= vadState.maxChunkDuration) {
            sendAudioChunk(false);
        }
        
    } catch (error) {
        // Silently fail for audio processing errors
        // print(`Captions: Error processing audio - ${error.message}`);
    }
}

function sendAudioChunk(isFinal) {
    if (audioBuffer.length === 0) {
        return;
    }
    
    try {
        // Combine all buffered chunks
        const totalLength = audioBuffer.reduce((sum, chunk) => sum + chunk.byteLength, 0);
        const combinedBuffer = new Uint8Array(totalLength);
        let offset = 0;
        
        audioBuffer.forEach(function(chunk) {
            const uint8Chunk = new Uint8Array(chunk);
            combinedBuffer.set(uint8Chunk, offset);
            offset += uint8Chunk.length;
        });
        
        // Send via WebSocket
        script.apiClient.sendAudioChunk(combinedBuffer.buffer, isFinal);
        
        // Clear buffer
        audioBuffer = [];
        
    } catch (error) {
        print(`Captions: Error sending audio chunk: ${error.message}`);
    }
}

function updateCaption(text, speaker = null) {
    currentCaption = text;
    
    // Format with speaker if available
    const displayText = speaker ? `${speaker}: ${text}` : text;
    
    // Update caption text component
    if (captionText) {
        // captionText.getComponent("Text").text = displayText;
        print(`Captions: Updated - ${displayText}`);
    }
    
    // Add to history (keep last 10)
    captionHistory.push({ text, speaker, timestamp: new Date() });
    if (captionHistory.length > 10) {
        captionHistory.shift();
    }
}

function updateTranslation(text) {
    currentTranslation = text;
    
    // Update translation text component
    if (translationText) {
        // translationText.getComponent("Text").text = text;
        print(`Captions: Translation updated - ${text}`);
    }
}

function clearCaptions() {
    currentCaption = "";
    currentTranslation = "";
    
    if (captionText) {
        // captionText.getComponent("Text").text = "";
    }
    
    if (translationText) {
        // translationText.getComponent("Text").text = "";
    }
    
    captionHistory = [];
}

function showCaptions() {
    if (captionText) {
        captionText.enabled = true;
    }
    if (translationText) {
        translationText.enabled = true;
    }
}

function hideCaptions() {
    if (captionText) {
        captionText.enabled = false;
    }
    if (translationText) {
        translationText.enabled = false;
    }
}

function setCaptionPosition(position) {
    if (captionText) {
        captionText.getTransform().setWorldPosition(position);
    }
}

function setTranslationPosition(position) {
    if (translationText) {
        translationText.getTransform().setWorldPosition(position);
    }
}

// Public API - assign methods directly to script (script.api is read-only)
script.enable = function() {
    isEnabled = true;
    startAudioCapture();
    showCaptions();
    print("Captions: Enabled");
};

script.disable = function() {
    isEnabled = false;
    hideCaptions();
    clearCaptions();
    
    // Send any remaining audio
    if (audioBuffer.length > 0) {
        sendAudioChunk(true);
    }
    
    // Disable microphone
    if (microphoneAudioProvider) {
        microphoneAudioProvider.enabled = false;
    }
    
    // Clear audio buffer
    audioBuffer = [];
    vadState.isSpeech = false;
    vadState.silenceDuration = 0;
    vadState.speechDuration = 0;
    
    print("Captions: Disabled");
};

script.updateCaption = updateCaption;
script.updateTranslation = updateTranslation;
script.showCaptions = showCaptions;
script.hideCaptions = hideCaptions;
script.setCaptionPosition = setCaptionPosition;
script.setTranslationPosition = setTranslationPosition;
script.getHistory = () => captionHistory;

// Initialize
initialize();

