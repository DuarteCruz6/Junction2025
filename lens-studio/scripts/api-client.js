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
        this.audioWebSocket = null;
        this.wsBaseUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://');
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
            
            // Connect audio WebSocket
            try {
                await this.connectAudioStream();
            } catch (error) {
                print(`Warning: Could not connect audio stream: ${error.message}`);
            }
            
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
            
            // Disconnect audio WebSocket
            this.endAudioStream();
            this.disconnectAudioStream();
            
            print(`Meeting stopped: ${this.currentMeetingId}`);
            return data;
        } catch (error) {
            print(`Error stopping meeting: ${error.message}`);
            throw error;
        }
    }

    /**
     * Connect WebSocket for audio streaming
     * @returns {Promise<void>}
     */
    async connectAudioStream() {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting");
        }

        if (this.audioWebSocket && this.audioWebSocket.readyState === WebSocket.OPEN) {
            print("Audio WebSocket already connected");
            return;
        }

        return new Promise((resolve, reject) => {
            try {
                const wsUrl = `${this.wsBaseUrl}/ws/audio/${this.currentMeetingId}`;
                this.audioWebSocket = new WebSocket(wsUrl);

                this.audioWebSocket.onopen = () => {
                    print(`Audio WebSocket connected for meeting ${this.currentMeetingId}`);
                    resolve();
                };

                this.audioWebSocket.onmessage = (event) => {
                    try {
                        const message = JSON.parse(event.data);
                        this.handleAudioMessage(message);
                    } catch (error) {
                        print(`Error parsing WebSocket message: ${error.message}`);
                    }
                };

                this.audioWebSocket.onerror = (error) => {
                    print(`Audio WebSocket error: ${error}`);
                    reject(error);
                };

                this.audioWebSocket.onclose = () => {
                    print("Audio WebSocket closed");
                    this.audioWebSocket = null;
                };
            } catch (error) {
                print(`Error creating WebSocket: ${error.message}`);
                reject(error);
            }
        });
    }

    /**
     * Handle incoming WebSocket messages
     * @param {Object} message - WebSocket message
     */
    handleAudioMessage(message) {
        switch (message.type) {
            case "connected":
                print(`Audio streaming ready: ${message.data.message}`);
                break;
            case "transcription_result":
                // Trigger callback if available
                if (this.onTranscriptionResult) {
                    this.onTranscriptionResult(message.data);
                }
                break;
            case "transcription_error":
                print(`Transcription error: ${message.data.error}`);
                if (this.onTranscriptionError) {
                    this.onTranscriptionError(message.data.error);
                }
                break;
            case "audio_received":
                // Acknowledgment - audio chunk received
                break;
            case "pong":
                // Keep-alive response
                break;
            default:
                print(`Unknown message type: ${message.type}`);
        }
    }

    /**
     * Send audio chunk via WebSocket
     * @param {ArrayBuffer|Uint8Array} audioData - PCM audio data
     * @param {boolean} isFinal - Whether this is the final chunk
     */
    sendAudioChunk(audioData, isFinal = false) {
        if (!this.audioWebSocket || this.audioWebSocket.readyState !== WebSocket.OPEN) {
            print("Audio WebSocket not connected");
            return;
        }

        try {
            // Send binary data directly (PCM format)
            this.audioWebSocket.send(audioData);
        } catch (error) {
            print(`Error sending audio chunk: ${error.message}`);
        }
    }

    /**
     * End audio stream
     */
    endAudioStream() {
        if (this.audioWebSocket && this.audioWebSocket.readyState === WebSocket.OPEN) {
            try {
                this.audioWebSocket.send(JSON.stringify({
                    type: "end_stream"
                }));
            } catch (error) {
                print(`Error ending audio stream: ${error.message}`);
            }
        }
    }

    /**
     * Disconnect audio WebSocket
     */
    disconnectAudioStream() {
        if (this.audioWebSocket) {
            this.audioWebSocket.close();
            this.audioWebSocket = null;
        }
    }

    /**
     * Send audio chunk for real-time STT processing (legacy HTTP method)
     * @param {ArrayBuffer} audioData - Audio data chunk
     * @returns {Promise<Object>} STT result with transcript and speaker info
     */
    async sendAudioChunkHTTP(audioData) {
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

    /**
     * Send transcription from Lens Studio ASR to backend
     * @param {string} text - Transcribed text
     * @param {boolean} isFinal - Whether this is a final transcription
     * @param {string} speaker - Optional speaker identifier
     * @returns {Promise<Object>} Response from backend
     */
    async sendTranscription(text, isFinal = false, speaker = "Unknown") {
        if (!this.currentMeetingId) {
            throw new Error("No active meeting");
        }

        if (!text || text.trim().length === 0) {
            // Skip empty transcriptions
            return { success: true, skipped: true };
        }

        try {
            const response = await fetch(`${this.baseUrl}/api/transcriptions/${this.currentMeetingId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    segments: [{
                        text: text.trim(),
                        speaker: speaker,
                        is_final: isFinal,
                    }]
                }),
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            return data;
        } catch (error) {
            print(`Error sending transcription: ${error.message}`);
            throw error;
        }
    }
}

// Export singleton instance
const apiClient = new APIClient();

// Make available globally
script.apiClient = apiClient;

