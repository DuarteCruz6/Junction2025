# Lens Studio Project - Enterprise Meeting AR

This directory contains the Snapchat Lens Studio project for the Spectacles AR glasses application.

## Overview

The Lens Studio project provides the AR interface for enterprise meetings, featuring:
- Real-time speech-to-text captions
- Live meeting summarization
- Task extraction and display
- Person detection and identification
- Interactive UI with hand gesture controls
- Settings page

## Prerequisites

1. **Lens Studio** - Download from [Snap Lens Studio](https://lensstudio.snapchat.com/)
2. **Backend API** - Must be running at `http://localhost:8000` (or configured endpoint)

## Project Structure

```
lens-studio/
├── scripts/
│   ├── controller.js          # Main controller - start/stop AI, state management
│   ├── api-client.js          # HTTP client for backend API communication
│   ├── ui-manager.js          # UI element management (summaries, tasks, captions)
│   ├── hand-tracking.js       # Hand gesture interactions (pinch, move, hide)
│   ├── captions.js            # Live captions and translations display
│   └── settings.js            # Settings page UI and logic
├── resources/                 # Assets, textures, materials
└── README.md                  # This file
```

## Setup Instructions

1. **Open in Lens Studio:**
   - Launch Lens Studio
   - File → Open Project → Select this directory
   - Or create a new project and copy the scripts

2. **Configure Backend URL:**
   - Edit `scripts/api-client.js`
   - Update `API_BASE_URL` to match your backend endpoint

3. **Test Connection:**
   - Ensure backend is running (`docker compose up` in backend/)
   - Use the start/stop button in the Lens to test API connection

## Features Implementation

### 1. Start/Stop Button
- **Script:** `controller.js`
- **Functionality:** Toggles AI processing on/off
- **Visual:** Button overlay in AR space

### 2. Live Captions/Translations
- **Script:** `captions.js`
- **Functionality:** Displays real-time speech-to-text
- **Position:** Configurable in AR space
- **Interactive:** Can be moved/hidden with hand gestures

### 3. Meeting Summarization
- **Script:** `ui-manager.js`
- **Functionality:** Displays periodic meeting summaries
- **Updates:** Real-time as meeting progresses
- **Interactive:** Pinchable, movable, hideable

### 4. Tasks Display
- **Script:** `ui-manager.js`
- **Functionality:** Shows extracted tasks from meetings
- **Features:** Due dates, task status
- **Interactive:** Full gesture support

### 5. Settings Page
- **Script:** `settings.js`
- **Functionality:** User preferences, API configuration
- **Access:** Gesture-based menu

### 6. Hand Gesture Interactions
- **Script:** `hand-tracking.js`
- **Gestures:**
  - **Pinch:** Select/move UI elements
  - **Drag:** Reposition elements
  - **Hide:** Swipe away elements
  - **Show:** Gesture to bring back hidden elements

## API Integration

The Lens Studio scripts communicate with the backend via HTTP:

- **POST** `/api/meetings/start` - Start meeting recording
- **POST** `/api/meetings/stop` - Stop meeting recording
- **POST** `/api/audio/stream` - Stream audio for STT
- **GET** `/api/meetings/{id}/summary` - Get meeting summary
- **GET** `/api/meetings/{id}/tasks` - Get extracted tasks
- **GET** `/api/meetings` - Get meeting history

## Development Tips

1. **Testing without Spectacles:**
   - Use Lens Studio's preview mode
   - Test with webcam/microphone input
   - Use Lens Studio's hand tracking simulation

2. **Debugging:**
   - Use `print()` statements (visible in Lens Studio console)
   - Check backend logs for API calls
   - Test API endpoints with Postman/curl first

3. **Performance:**
   - Keep UI updates efficient (throttle API calls)
   - Cache meeting summaries locally
   - Use WebSocket for real-time updates (if implemented)

## Deployment

1. **Build Lens:**
   - File → Export Lens
   - Follow Snapchat's submission process

2. **Backend Deployment:**
   - Deploy backend to production
   - Update API URL in `api-client.js`
   - Ensure CORS is configured for production domain

## Resources

- [Lens Studio Documentation](https://docs.snap.com/lens-studio/)
- [Lens Studio Scripting API](https://docs.snap.com/lens-studio/references/guides/scripting-overview)
- [Hand Tracking Guide](https://docs.snap.com/lens-studio/references/guides/input/hand-tracking)
- [Spectacles Development](https://docs.snap.com/spectacles/)

