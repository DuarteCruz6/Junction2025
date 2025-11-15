/**
 * Direct ASR Test Script
 * Simple test to start meeting and ASR transcription
 * Attach this to an entity - it will auto-start after 2 seconds
 */

// @input Component.ScriptComponent apiClientScript
// @input Component.ScriptComponent asrScript

print("=== ASR Direct Test: Initializing ===");

// Wait 2 seconds for everything to initialize, then start
const delayedEvent = script.createEvent("DelayedCallbackEvent");
delayedEvent.bind(function() {
    print("=== ASR Direct Test: Starting... ===");
    
    // Get API client
    const apiClient = script.apiClientScript ? script.apiClientScript.script.apiClient : script.apiClient;
    
    if (!apiClient) {
        print("=== ERROR: API client not found ===");
        return;
    }
    
    // Get ASR component
    const asrComponent = script.asrScript;
    
    if (!asrComponent) {
        print("=== ERROR: ASR script not found ===");
        print("=== Make sure to connect asrScript input ===");
        return;
    }
    
    // Start meeting first
    print("=== Starting meeting... ===");
    apiClient.startMeeting().then(function(meetingData) {
        print("=== Meeting started! ID: " + meetingData.meeting_id + " ===");
        
        // Wait a moment, then start ASR
        const asrDelay = script.createEvent("DelayedCallbackEvent");
        asrDelay.bind(function() {
            print("=== Starting ASR transcription... ===");
            if (asrComponent.startTranscribing) {
                asrComponent.startTranscribing();
                print("=== ASR started! Speak into microphone now! ===");
                print("=== Will auto-stop after 60 seconds ===");
                
                // Auto-stop after 60 seconds
                const stopDelay = script.createEvent("DelayedCallbackEvent");
                stopDelay.bind(function() {
                    if (asrComponent.stopTranscribing) {
                        asrComponent.stopTranscribing();
                        print("=== ASR stopped ===");
                    }
                    if (apiClient.stopMeeting) {
                        apiClient.stopMeeting();
                        print("=== Meeting stopped ===");
                    }
                });
                stopDelay.reset(60.0);
            } else {
                print("=== ERROR: startTranscribing method not found ===");
            }
        });
        asrDelay.reset(1.0); // Wait 1 second after meeting starts
        
    }).catch(function(error) {
        print("=== ERROR starting meeting: " + error.message + " ===");
    });
});
delayedEvent.reset(2.0); // Wait 2 seconds before starting

print("=== ASR Direct Test: Will start in 2 seconds ===");
