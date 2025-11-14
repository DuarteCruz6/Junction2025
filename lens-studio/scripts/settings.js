/**
 * Settings Script
 * Manages the settings page UI and user preferences
 */

// @input Component.ScriptComponent apiClientScript

const settings = script.apiContext.entity;

// Settings state
let isSettingsOpen = false;
let settingsPanel = null;

// User preferences
let preferences = {
    showCaptions: true,
    showTranslations: true,
    showSummary: true,
    showTasks: true,
    captionPosition: { x: 0, y: -0.3, z: -1 },
    summaryPosition: { x: 0.3, y: 0.2, z: -1 },
    tasksPosition: { x: -0.3, y: 0.2, z: -1 },
    apiUrl: "http://localhost:8000",
    updateInterval: 2000, // milliseconds
};

function initialize() {
    print("Settings: Initializing...");
    
    // Load saved preferences
    loadPreferences();
    
    // Create settings panel
    createSettingsPanel();
    
    print("Settings: Initialized");
}

function createSettingsPanel() {
    // Create settings UI panel
    // This will be configured in Lens Studio scene
    // Should include toggles, sliders, text inputs
    
    print("Settings: Settings panel created");
}

function loadPreferences() {
    // Load preferences from local storage or default values
    // In Lens Studio, you might use Global Storage or similar
    
    try {
        // Example: const saved = global.storage.get("preferences");
        // if (saved) preferences = JSON.parse(saved);
        print("Settings: Preferences loaded");
    } catch (error) {
        print(`Settings: Error loading preferences - ${error.message}`);
    }
}

function savePreferences() {
    // Save preferences to local storage
    
    try {
        // Example: global.storage.set("preferences", JSON.stringify(preferences));
        print("Settings: Preferences saved");
    } catch (error) {
        print(`Settings: Error saving preferences - ${error.message}`);
    }
}

function openSettings() {
    isSettingsOpen = true;
    if (settingsPanel) {
        settingsPanel.enabled = true;
    }
    print("Settings: Opened");
}

function closeSettings() {
    isSettingsOpen = false;
    if (settingsPanel) {
        settingsPanel.enabled = false;
    }
    savePreferences();
    print("Settings: Closed");
}

function toggleSetting(settingName) {
    if (preferences.hasOwnProperty(settingName)) {
        preferences[settingName] = !preferences[settingName];
        savePreferences();
        applySetting(settingName);
        print(`Settings: Toggled ${settingName} - ${preferences[settingName]}`);
    }
}

function updateSetting(settingName, value) {
    if (preferences.hasOwnProperty(settingName)) {
        preferences[settingName] = value;
        savePreferences();
        applySetting(settingName);
        print(`Settings: Updated ${settingName} - ${value}`);
    }
}

function applySetting(settingName) {
    // Apply setting changes to UI components
    switch (settingName) {
        case "showCaptions":
            if (script.captionsScript) {
                if (preferences.showCaptions) {
                    script.captionsScript.api.showCaptions();
                } else {
                    script.captionsScript.api.hideCaptions();
                }
            }
            break;
            
        case "showSummary":
            if (script.uiManagerScript) {
                if (preferences.showSummary) {
                    script.uiManagerScript.api.showSummary();
                } else {
                    script.uiManagerScript.api.hideSummary();
                }
            }
            break;
            
        case "showTasks":
            if (script.uiManagerScript) {
                if (preferences.showTasks) {
                    script.uiManagerScript.api.showTasks();
                } else {
                    script.uiManagerScript.api.hideTasks();
                }
            }
            break;
            
        case "apiUrl":
            // Update API client URL
            if (script.apiClientScript) {
                script.apiClientScript.api.baseUrl = preferences.apiUrl;
            }
            break;
    }
}

function getPreferences() {
    return preferences;
}

// Public API
script.api = {
    open: openSettings,
    close: closeSettings,
    toggle: toggleSetting,
    update: updateSetting,
    getPreferences: getPreferences,
    isOpen: () => isSettingsOpen,
};

// Initialize
initialize();

// Gesture to open settings (configure in Lens Studio)
// Example: Long press or specific hand gesture
const settingsGesture = script.createEvent("TapEvent");
settingsGesture.bind(function() {
    // Toggle settings on long tap or specific gesture
    if (isSettingsOpen) {
        closeSettings();
    } else {
        openSettings();
    }
});

