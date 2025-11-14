/**
 * Captions Script
 * Displays real-time speech-to-text captions and translations
 * Updates as audio is processed by the backend
 */

// @input Component.ScriptComponent apiClientScript
// @input Component.AudioComponent audioComponent

const captions = script.apiContext.entity;

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
    if (!script.audioComponent) {
        print("Captions: No audio component available");
        return;
    }
    
    // Start capturing audio and sending to backend
    // Note: Actual audio capture depends on Lens Studio's audio API
    // This is a placeholder for the implementation
    
    audioUpdateInterval = script.createEvent("UpdateEvent");
    audioUpdateInterval.bind(function() {
        if (isEnabled) {
            processAudioChunk();
        }
    });
    
    print("Captions: Audio capture started");
}

async function processAudioChunk() {
    if (!isEnabled || !script.apiClient.isRecording) return;
    
    try {
        // Get audio data from microphone
        // Note: This depends on Lens Studio's audio capture API
        // const audioData = getAudioChunk();
        
        // Send to backend for STT processing
        // const result = await script.apiClient.sendAudioChunk(audioData);
        
        // Update captions with result
        // if (result && result.transcript) {
        //     updateCaption(result.transcript, result.speaker);
        //     if (result.translation) {
        //         updateTranslation(result.translation);
        //     }
        // }
    } catch (error) {
        // Silently fail for audio processing errors
        // print(`Captions: Error processing audio - ${error.message}`);
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

// Public API
script.api = {
    enable: function() {
        isEnabled = true;
        startAudioCapture();
        showCaptions();
        print("Captions: Enabled");
    },
    
    disable: function() {
        isEnabled = false;
        hideCaptions();
        clearCaptions();
        print("Captions: Disabled");
    },
    
    updateCaption: updateCaption,
    updateTranslation: updateTranslation,
    showCaptions: showCaptions,
    hideCaptions: hideCaptions,
    setCaptionPosition: setCaptionPosition,
    setTranslationPosition: setTranslationPosition,
    getHistory: () => captionHistory,
};

// Initialize
initialize();

