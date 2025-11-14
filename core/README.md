# Core

This folder is intended for shared code and resources that can be used across the web app, mobile app, and backend.

## Current Structure

```
core/
├── types/          # Shared TypeScript types/interfaces
├── constants/      # Shared constants
└── utils/          # Shared utility functions
```

## Usage

This folder is intended for code that needs to be shared between different parts of the application. As the project grows, you can add:

- Type definitions for API requests/responses
- Shared constants (API endpoints, configuration values)
- Utility functions that are used across platforms

## Note on ML Models

**Important:** If you plan to store ML models in this folder, consider the following:

- ML model files are typically large (hundreds of MB to GB) and should be added to `.gitignore`
- Models are usually Python-specific and loaded by the backend
- Consider using a separate `models/` subdirectory within `core/` or `backend/` for better organization
- You may want to use Git LFS (Large File Storage) for version control of model files

See the main README.md for recommendations on ML model organization.

