/**
 * Shared TypeScript types and interfaces
 * These types can be used across web app, mobile app, and backend (via type generation)
 */

// Example: API Response types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

// Example: User types
export interface User {
  id: string;
  name: string;
  email: string;
}

// Add more shared types as needed

