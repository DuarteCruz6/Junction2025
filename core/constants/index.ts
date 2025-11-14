/**
 * Shared constants across the application
 */

// API Configuration
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
export const API_ENDPOINTS = {
  HEALTH: '/health',
  // Add more endpoints as needed
} as const;

// Add more constants as needed

