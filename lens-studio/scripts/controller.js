/**
 * Main Controller Script
 * Manages the overall state of the AR application
 * Handles start/stop button and coordinates other modules
 */

// @input Component.ScriptComponent apiClientScript
// @input Component.ScriptComponent uiManagerScript
// @input Component.ScriptComponent captionsScript
// @input Component.ScriptComponent handTrackingScript
// @input Component.ScriptComponent asrScript
// @input Component.ScriptComponent meeting_text
// @input Component.ScriptComponent touch_events

// Get controller entity safely (if needed)
// const controller = (script.apiContext && script.apiContext.entity) ? script.apiContext.entity : null;

// Application state
let isAIActive = false;
let meetingStartTime = null;
let updateInterval = null;

// UI References
let startStopButton = null;
let statusIndicator = null;

// Store API client reference (don't assign to script.apiClient - it's read-only)
let apiClient = null;

function initialize() {
    print("=== Controller: Initializing... ===");
    
    // Get API client from script component or global
    if (script.apiClientScript && script.apiClientScript.script) {
        apiClient = script.apiClientScript.script.apiClient;
        print("=== Controller: API client connected via script component ===");
    } else if (typeof script.apiClient !== "undefined") {
        apiClient = script.apiClient;
        print("=== Controller: API client already available globally ===");
    } else {
        print("=== Controller: Warning - API client not found ===");
    }
    
    // Set up initial text
    if (script.meeting_text) {
        try {
            script.meeting_text.text = "Tap to start meeting.";
        } catch (e) {
            print("Controller: Could not set initial text - " + e);
        }
    }
    
    // Set up periodic updates
    setupPeriodicUpdates();
    
    // Set up tap handler
    setupTapHandler();
    
    print("=== Controller: Initialized ===");
    print("=== Controller: ASR Script available: " + (script.asrScript ? "YES" : "NO") + " ===");
    print("=== Controller: API Client available: " + (script.apiClient ? "YES" : "NO") + " ===");
}

function setupTapHandler() {
    if (script.touch_events) {
        script.touch_events.onTap.add(function(tapX, tapY) {
            handleTap();
        });
        print("=== Controller: Tap handler configured ===");
    } else {
        print("=== Controller: Warning - touch_events not connected ===");
        // Fallback: Use TapEvent
        const tapEvent = script.createEvent("TapEvent");
        tapEvent.bind(function() {
            print("=== TapEvent triggered (fallback) ===");
            handleTap();
        });
    }
}

function setupPeriodicUpdates() {
    // Update UI every 2 seconds when AI is active
    updateInterval = script.createEvent("UpdateEvent");
    updateInterval.bind(function() {
        if (isAIActive) {
            updateUI();
        }
    });
}

function handleTap() {
    print("=== handleTap() called ===");
    if (!isAIActive) {
        // Start meeting and AI
        startAI().catch(function(error) {
            print("Controller: Error starting AI - " + error.message);
            if (script.meeting_text) {
                try {
                    script.meeting_text.text = "Error: " + error.message;
                } catch (e) {}
            }
        });
    } else {
        // Stop meeting and AI
        stopAI().catch(function(error) {
            print("Controller: Error stopping AI - " + error.message);
        });
    }
}

async function toggleAI() {
    try {
        if (!isAIActive) {
            // Start AI
            await startAI();
        } else {
            // Stop AI
            await stopAI();
        }
    } catch (error) {
        print(`Controller: Error toggling AI - ${error.message}`);
    }
}

async function startAI() {
    print("Controller: Starting AI...");
    
    // Update text
    if (script.meeting_text) {
        try {
            script.meeting_text.text = "Meeting is starting...";
        } catch (e) {}
    }
    
    // Disable touch events while starting
    if (script.touch_events) {
        script.touch_events.enabled = false;
    }
    
    try {
        // Start meeting session
        const client = apiClient || script.apiClient;
        if (!client) {
            throw new Error("API client not available");
        }
        const meetingData = await client.startMeeting();
        meetingStartTime = new Date();
        isAIActive = true;
        
        // Update text
        if (script.meeting_text) {
            try {
                script.meeting_text.text = "Meeting active. Tap to stop.";
            } catch (e) {}
        }
        
        // Re-enable touch events
        if (script.touch_events) {
            script.touch_events.enabled = true;
        }
        
        // Start ASR transcription
        if (script.asrScript) {
            try {
                // Access public methods directly from TypeScript component
                if (script.asrScript.startTranscribing) {
                    script.asrScript.startTranscribing();
                    print("Controller: ASR transcription started");
                } else {
                    print("Controller: Warning - startTranscribing method not found on ASR script");
                }
            } catch (error) {
                print(`Controller: Warning - Could not start ASR: ${error.message}`);
            }
        } else {
            print("Controller: Warning - ASR script not found or not configured");
        }
        
        // Enable UI components
        if (script.captionsScript && script.captionsScript.enable) {
            script.captionsScript.enable();
        }
        
        if (script.uiManagerScript && script.uiManagerScript.api && script.uiManagerScript.api.enable) {
            script.uiManagerScript.api.enable();
        }
        
        // Update button state
        updateButtonState(true);
        
        print(`Controller: AI started - Meeting ID: ${meetingData.meeting_id}`);
    } catch (error) {
        print(`Controller: Failed to start AI - ${error.message}`);
        // Update text on error
        if (script.meeting_text) {
            try {
                script.meeting_text.text = "Error: " + error.message + ". Tap to retry.";
            } catch (e) {}
        }
        // Re-enable touch events on error
        if (script.touch_events) {
            script.touch_events.enabled = true;
        }
        throw error;
    }
}

async function stopAI() {
    print("Controller: Stopping AI...");
    
    // Update text
    if (script.meeting_text) {
        try {
            script.meeting_text.text = "Stopping meeting...";
        } catch (e) {}
    }
    
    // Disable touch events while stopping
    if (script.touch_events) {
        script.touch_events.enabled = false;
    }
    
    try {
        // Stop ASR transcription first
        if (script.asrScript) {
            try {
                // Access public methods directly from TypeScript component
                if (script.asrScript.stopTranscribing) {
                    script.asrScript.stopTranscribing();
                    print("Controller: ASR transcription stopped");
                }
            } catch (error) {
                print(`Controller: Warning - Could not stop ASR: ${error.message}`);
            }
        }
        
        // Stop meeting session
        const client = apiClient || script.apiClient;
        if (!client) {
            throw new Error("API client not available");
        }
        const meetingData = await client.stopMeeting();
        isAIActive = false;
        meetingStartTime = null;
        
        // Update text
        if (script.meeting_text) {
            try {
                script.meeting_text.text = "Tap to start meeting.";
            } catch (e) {}
        }
        
        // Re-enable touch events
        if (script.touch_events) {
            script.touch_events.enabled = true;
        }
        
        // Disable UI components
        if (script.captionsScript && script.captionsScript.disable) {
            script.captionsScript.disable();
        }
        
        if (script.uiManagerScript && script.uiManagerScript.api && script.uiManagerScript.api.disable) {
            script.uiManagerScript.api.disable();
        }
        
        // Update button state
        updateButtonState(false);
        
        print(`Controller: AI stopped - Meeting ID: ${meetingData.meeting_id}`);
    } catch (error) {
        print(`Controller: Failed to stop AI - ${error.message}`);
        // Update text on error
        if (script.meeting_text) {
            try {
                script.meeting_text.text = "Error stopping. Tap to retry.";
            } catch (e) {}
        }
        // Re-enable touch events on error
        if (script.touch_events) {
            script.touch_events.enabled = true;
        }
        throw error;
    }
}

function updateButtonState(isActive) {
    // Update button visual state
    // This depends on your button implementation
    if (startStopButton) {
        // Example: Change texture, color, etc.
        print(`Controller: Button state updated - Active: ${isActive}`);
    }
}

async function updateUI() {
    if (!isAIActive) return;
    
    try {
        const client = apiClient || script.apiClient;
        if (!client) return;
        
        // Get latest summary
        const summary = await client.getMeetingSummary();
        if (script.uiManagerScript && script.uiManagerScript.api && script.uiManagerScript.api.updateSummary && summary) {
            script.uiManagerScript.api.updateSummary(summary);
        }
        
        // Get latest tasks
        const tasks = await client.getTasks();
        if (script.uiManagerScript && script.uiManagerScript.api && script.uiManagerScript.api.updateTasks && tasks) {
            script.uiManagerScript.api.updateTasks(tasks);
        }
    } catch (error) {
        // Silently fail - don't spam errors
        // print(`Controller: Error updating UI - ${error.message}`);
    }
}

// Public API - initialize in onAwake or use getter pattern
// Note: script.api is read-only, so we'll expose methods directly on script
script.toggleAI = toggleAI;
script.isActive = () => isAIActive;
script.getMeetingId = () => {
    const client = apiClient || script.apiClient;
    return client ? client.currentMeetingId : null;
};
// Test function - can be called directly
script.testASR = async function() {
    print("Test: Starting meeting and ASR...");
    await startAI();
    print("Test: Meeting started. Speak into microphone now!");
    print("Test: Will auto-stop after 30 seconds...");
    setTimeout(async () => {
        await stopAI();
        print("Test: Stopped");
    }, 30000);
};

// Initialize on start
try {
    initialize();
} catch (e) {
    print("=== Controller: Error in initialize ===");
    print(e);
}

