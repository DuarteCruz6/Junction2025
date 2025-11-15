/**
 * Simple Test Script
 * Add this to an entity to verify scripts are running
 */

print("=== TEST SCRIPT: Starting ===");

// Test print on update
const updateEvent = script.createEvent("UpdateEvent");
updateEvent.bind(function() {
    print("=== TEST: UpdateEvent fired ===");
    updateEvent.enabled = false; // Only run once
});

print("=== TEST SCRIPT: Initialized ===");

