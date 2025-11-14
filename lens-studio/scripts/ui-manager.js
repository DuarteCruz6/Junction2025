/**
 * UI Manager Script
 * Manages all UI elements: summaries, tasks, captions
 * Handles positioning, visibility, and updates
 */

// @input Component.ScriptComponent apiClientScript

const uiManager = script.apiContext.entity;

// UI Elements
let summaryPanel = null;
let tasksPanel = null;
let isEnabled = false;

// UI State
let currentSummary = null;
let currentTasks = [];

function initialize() {
    print("UI Manager: Initializing...");
    
    // Create UI panels
    createSummaryPanel();
    createTasksPanel();
    
    print("UI Manager: Initialized");
}

function createSummaryPanel() {
    // Create summary display panel
    // This will be configured in Lens Studio scene
    // Example: Text component or plane with text texture
    
    print("UI Manager: Summary panel created");
}

function createTasksPanel() {
    // Create tasks display panel
    // This will be configured in Lens Studio scene
    
    print("UI Manager: Tasks panel created");
}

function updateSummary(summaryData) {
    if (!isEnabled) return;
    
    currentSummary = summaryData;
    
    // Update summary text display
    if (summaryPanel && summaryData) {
        const summaryText = summaryData.summary || "No summary yet...";
        // Update text component
        // Example: summaryPanel.getComponent("Text").text = summaryText;
        
        print(`UI Manager: Summary updated - ${summaryText.substring(0, 50)}...`);
    }
}

function updateTasks(tasksArray) {
    if (!isEnabled) return;
    
    currentTasks = tasksArray || [];
    
    // Update tasks display
    if (tasksPanel && currentTasks.length > 0) {
        // Format tasks for display
        const tasksText = formatTasksForDisplay(currentTasks);
        // Update text component
        // Example: tasksPanel.getComponent("Text").text = tasksText;
        
        print(`UI Manager: Tasks updated - ${currentTasks.length} tasks`);
    }
}

function formatTasksForDisplay(tasks) {
    let text = "Tasks:\n";
    tasks.forEach((task, index) => {
        const dueDate = task.due_date ? ` (Due: ${task.due_date})` : "";
        text += `${index + 1}. ${task.description}${dueDate}\n`;
    });
    return text;
}

function showSummary() {
    if (summaryPanel) {
        summaryPanel.enabled = true;
    }
}

function hideSummary() {
    if (summaryPanel) {
        summaryPanel.enabled = false;
    }
}

function showTasks() {
    if (tasksPanel) {
        tasksPanel.enabled = true;
    }
}

function hideTasks() {
    if (tasksPanel) {
        tasksPanel.enabled = false;
    }
}

function setSummaryPosition(position) {
    if (summaryPanel) {
        summaryPanel.getTransform().setWorldPosition(position);
    }
}

function setTasksPosition(position) {
    if (tasksPanel) {
        tasksPanel.getTransform().setWorldPosition(position);
    }
}

// Public API
script.api = {
    enable: function() {
        isEnabled = true;
        showSummary();
        showTasks();
        print("UI Manager: Enabled");
    },
    
    disable: function() {
        isEnabled = false;
        hideSummary();
        hideTasks();
        print("UI Manager: Disabled");
    },
    
    updateSummary: updateSummary,
    updateTasks: updateTasks,
    showSummary: showSummary,
    hideSummary: hideSummary,
    showTasks: showTasks,
    hideTasks: hideTasks,
    setSummaryPosition: setSummaryPosition,
    setTasksPosition: setTasksPosition,
};

// Initialize
initialize();

