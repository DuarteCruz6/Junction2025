/**
 * Main Controller Script
 * Manages the overall state of the AR application
 * Handles start/stop button and coordinates other modules
 */

// @input Component.ScriptComponent apiClientScript
// @input Component.ScriptComponent uiManagerScript
// @input Component.ScriptComponent captionsScript
// @input Component.ScriptComponent handTrackingScript

const controller = script.apiContext.entity;

// Application state
let isAIActive = false;
let meetingStartTime = null;
let updateInterval = null;

// UI References
let startStopButton = null;
let statusIndicator = null;

function initialize() {
    print("Controller: Initializing...");
    
    // Create start/stop button
    createStartStopButton();
    
    // Set up periodic updates
    setupPeriodicUpdates();
    
    print("Controller: Initialized");
}

function createStartStopButton() {
    // Create button entity (you'll need to set this up in Lens Studio scene)
    // This is a placeholder - actual implementation depends on your scene setup
    
    // Example: Create a plane with texture for the button
    // You'll configure this in Lens Studio's visual editor
    
    print("Controller: Start/Stop button created");
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
    
    try {
        // Start meeting session
        const meetingData = await script.apiClient.startMeeting();
        meetingStartTime = new Date();
        isAIActive = true;
        
        // Enable UI components
        if (script.captionsScript) {
            script.captionsScript.api.enable();
        }
        
        if (script.uiManagerScript) {
            script.uiManagerScript.api.enable();
        }
        
        // Update button state
        updateButtonState(true);
        
        print(`Controller: AI started - Meeting ID: ${meetingData.meeting_id}`);
    } catch (error) {
        print(`Controller: Failed to start AI - ${error.message}`);
        throw error;
    }
}

async function stopAI() {
    print("Controller: Stopping AI...");
    
    try {
        // Stop meeting session
        const meetingData = await script.apiClient.stopMeeting();
        isAIActive = false;
        meetingStartTime = null;
        
        // Disable UI components
        if (script.captionsScript) {
            script.captionsScript.api.disable();
        }
        
        if (script.uiManagerScript) {
            script.uiManagerScript.api.disable();
        }
        
        // Update button state
        updateButtonState(false);
        
        print(`Controller: AI stopped - Meeting ID: ${meetingData.meeting_id}`);
    } catch (error) {
        print(`Controller: Failed to stop AI - ${error.message}`);
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
        // Get latest summary
        const summary = await script.apiClient.getMeetingSummary();
        if (script.uiManagerScript && summary) {
            script.uiManagerScript.api.updateSummary(summary);
        }
        
        // Get latest tasks
        const tasks = await script.apiClient.getTasks();
        if (script.uiManagerScript && tasks) {
            script.uiManagerScript.api.updateTasks(tasks);
        }
    } catch (error) {
        // Silently fail - don't spam errors
        // print(`Controller: Error updating UI - ${error.message}`);
    }
}

// Public API
script.api = {
    toggleAI: toggleAI,
    isActive: () => isAIActive,
    getMeetingId: () => script.apiClient.currentMeetingId,
};

// Initialize on start
initialize();

// Handle button tap (configure in Lens Studio)
const tapEvent = script.createEvent("TapEvent");
tapEvent.bind(function() {
    toggleAI();
});

