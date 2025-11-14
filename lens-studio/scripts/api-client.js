/**
 * API Client for Backend Communication
 * Handles all HTTP requests to the FastAPI backend
 */

// @input Asset.Texture apiIcon

const API_BASE_URL = "http://localhost:8000"; // Update for production

// API Client Class
class APIClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
        this.currentMeetingId = null;
        this.isRecording = false;
    }

    /**
     * Start a new meeting session
     * @returns {Promise<Object>} Meeting session data
     */
    async startMeeting() {
        try {
            const response = await fetch(`${this.baseUrl}/api/meetings/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.currentMeetingId = data.meeting_id;
            this.isRecording = true;
            
            print(`Meeting started: ${this.currentMeetingId}`);
            return data;
        } catch (error) {
            print(`Error starting meeting: ${error.message}`);
            throw error;
        }
    }

    /**
     * Stop the current meeting session
     * @returns {Promise<Object>} Final meeting data
     */
    async stopMeeting() {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting to stop");
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/meetings/${this.currentMeetingId}/stop`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            this.isRecording = false;
            
            print(`Meeting stopped: ${this.currentMeetingId}`);
            return data;
        } catch (error) {
            print(`Error stopping meeting: ${error.message}`);
            throw error;
        }
    }

    /**
     * Send audio chunk for real-time STT processing
     * @param {ArrayBuffer} audioData - Audio data chunk
     * @returns {Promise<Object>} STT result with transcript and speaker info
     */
    async sendAudioChunk(audioData) {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting");
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/audio/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/octet-stream',
                    'X-Meeting-ID': this.currentMeetingId,
                },
                body: audioData,
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            print(`Error sending audio: ${error.message}`);
            throw error;
        }
    }

    /**
     * Get current meeting summary
     * @returns {Promise<Object>} Meeting summary data
     */
    async getMeetingSummary() {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting");
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/meetings/${this.currentMeetingId}/summary`, {
                method: 'GET',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            print(`Error getting summary: ${error.message}`);
            throw error;
        }
    }

    /**
     * Get extracted tasks from current meeting
     * @returns {Promise<Array>} Array of task objects
     */
    async getTasks() {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting");
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/meetings/${this.currentMeetingId}/tasks`, {
                method: 'GET',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data.tasks || [];
        } catch (error) {
            print(`Error getting tasks: ${error.message}`);
            throw error;
        }
    }

    /**
     * Get meeting history
     * @returns {Promise<Array>} Array of past meetings
     */
    async getMeetingHistory() {
        try {
            const response = await fetch(`${this.baseUrl}/api/meetings`, {
                method: 'GET',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data.meetings || [];
        } catch (error) {
            print(`Error getting history: ${error.message}`);
            throw error;
        }
    }

    /**
     * Get specific meeting details
     * @param {string} meetingId - Meeting ID
     * @returns {Promise<Object>} Meeting details
     */
    async getMeetingDetails(meetingId) {
        try {
            const response = await fetch(`${this.baseUrl}/api/meetings/${meetingId}`, {
                method: 'GET',
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            print(`Error getting meeting details: ${error.message}`);
            throw error;
        }
    }
}

// Export singleton instance
const apiClient = new APIClient();

// Make available globally
script.apiClient = apiClient;

