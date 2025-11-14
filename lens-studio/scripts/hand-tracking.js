/**
 * Hand Tracking Script
 * Handles hand gesture interactions for UI elements
 * Supports pinch, drag, hide/show gestures
 */

// @input Component.HandTrackingComponent handTracking

const handTracking = script.apiContext.entity;

// Gesture state
let isPinching = false;
let selectedElement = null;
let pinchStartPosition = null;
let lastHandPosition = null;

// UI Elements that can be interacted with
let interactiveElements = [];

function initialize() {
    print("Hand Tracking: Initializing...");
    
    if (!script.handTracking) {
        print("Hand Tracking: Warning - No hand tracking component found");
        return;
    }
    
    // Set up gesture detection
    setupGestureDetection();
    
    print("Hand Tracking: Initialized");
}

function setupGestureDetection() {
    // Create update event for continuous hand tracking
    const updateEvent = script.createEvent("UpdateEvent");
    updateEvent.bind(function() {
        if (script.handTracking) {
            processHandGestures();
        }
    });
}

function processHandGestures() {
    // Get hand tracking data
    const hands = script.handTracking.getHands();
    
    if (hands.length === 0) {
        if (isPinching) {
            // Hand lost while pinching - release
            releaseElement();
        }
        return;
    }
    
    // Process first hand (can extend to support both hands)
    const hand = hands[0];
    const pinchStrength = hand.getPinchStrength();
    const handPosition = hand.getIndexTip().getWorldPosition();
    
    // Detect pinch gesture
    if (pinchStrength > 0.7 && !isPinching) {
        // Start pinch
        startPinch(handPosition);
    } else if (pinchStrength < 0.5 && isPinching) {
        // End pinch
        releaseElement();
    } else if (isPinching && selectedElement) {
        // Update drag position
        updateDrag(handPosition);
    }
    
    lastHandPosition = handPosition;
}

function startPinch(handPosition) {
    isPinching = true;
    pinchStartPosition = handPosition;
    
    // Find element at pinch position
    selectedElement = findElementAtPosition(handPosition);
    
    if (selectedElement) {
        print(`Hand Tracking: Pinched element - ${selectedElement.name}`);
        // Notify element it's being selected
        if (selectedElement.api && selectedElement.api.onSelect) {
            selectedElement.api.onSelect();
        }
    }
}

function updateDrag(handPosition) {
    if (!selectedElement) return;
    
    // Calculate movement delta
    const delta = handPosition.sub(pinchStartPosition);
    
    // Move element
    const currentPos = selectedElement.getTransform().getWorldPosition();
    const newPos = currentPos.add(delta);
    selectedElement.getTransform().setWorldPosition(newPos);
    
    // Update pinch start for next frame
    pinchStartPosition = handPosition;
}

function releaseElement() {
    if (selectedElement) {
        print(`Hand Tracking: Released element - ${selectedElement.name}`);
        // Notify element it's been released
        if (selectedElement.api && selectedElement.api.onRelease) {
            selectedElement.api.onRelease();
        }
    }
    
    isPinching = false;
    selectedElement = null;
    pinchStartPosition = null;
}

function findElementAtPosition(position) {
    // Find the closest interactive element to the pinch position
    let closestElement = null;
    let closestDistance = Infinity;
    
    for (let element of interactiveElements) {
        if (!element.enabled) continue;
        
        const elementPos = element.getTransform().getWorldPosition();
        const distance = position.sub(elementPos).length();
        
        // Check if within interaction radius (adjust as needed)
        const interactionRadius = 0.1; // meters
        
        if (distance < interactionRadius && distance < closestDistance) {
            closestDistance = distance;
            closestElement = element;
        }
    }
    
    return closestElement;
}

function registerInteractiveElement(element) {
    if (!interactiveElements.includes(element)) {
        interactiveElements.push(element);
        print(`Hand Tracking: Registered element - ${element.name}`);
    }
}

function unregisterInteractiveElement(element) {
    const index = interactiveElements.indexOf(element);
    if (index > -1) {
        interactiveElements.splice(index, 1);
        print(`Hand Tracking: Unregistered element - ${element.name}`);
    }
}

// Gesture: Hide element (swipe away)
function detectHideGesture(handPosition, handVelocity) {
    // Detect fast swipe gesture
    const swipeThreshold = 0.5; // m/s
    
    if (handVelocity.length() > swipeThreshold) {
        const element = findElementAtPosition(handPosition);
        if (element && element.api && element.api.hide) {
            element.api.hide();
            print(`Hand Tracking: Hid element - ${element.name}`);
        }
    }
}

// Gesture: Show element (bring back)
function detectShowGesture() {
    // Implement gesture to show hidden elements
    // This could be a specific hand pose or gesture
}

// Public API
script.api = {
    registerElement: registerInteractiveElement,
    unregisterElement: unregisterInteractiveElement,
    isPinching: () => isPinching,
    getSelectedElement: () => selectedElement,
};

// Initialize
initialize();

