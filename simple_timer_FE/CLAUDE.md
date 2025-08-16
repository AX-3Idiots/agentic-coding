# Simple Timer Frontend Application

## Project Overview
This is a simple timer application built with React, TypeScript, and Vite. The application provides a countdown timer with start, pause, and reset functionality.

## Architecture Decisions

### Component Structure
The project follows a feature-based architecture with the following key components:

#### 1. Timer Display Component (`src/components/ui/TimerDisplay.tsx`)
**Why**: Separates the visual representation of time from the timer logic, making it reusable and testable.
**What**: A pure presentational component that displays time in MM:SS format with large, readable digits.

#### 2. Timer Controls Component (`src/components/ui/TimerControls.tsx`)
**Why**: Encapsulates all timer control buttons (Start, Pause, Reset) in a single component for better organization and reusability.
**What**: Contains three buttons with appropriate styling and click handlers passed as props.

#### 3. Timer Input Component (`src/components/ui/TimerInput.tsx`)
**Why**: Provides a dedicated component for time input fields (minutes and seconds) with validation and formatting.
**What**: Two input fields with proper validation, number formatting, and accessibility features.

#### 4. Main Timer Feature (`src/features/timer/Timer.tsx`)
**Why**: Acts as the main container component that orchestrates all timer functionality and state management.
**What**: Manages timer state, countdown logic, and coordinates between all child components.

### Custom Hooks

#### 1. useTimer Hook (`src/hooks/useTimer.ts`)
**Why**: Separates timer logic from UI components, making the logic reusable and easier to test.
**What**: Manages timer state (time, isRunning, isPaused), countdown logic, and provides methods for start/pause/reset operations.

#### 2. useAudio Hook (`src/hooks/useAudio.ts`)
**Why**: Encapsulates audio playback functionality for timer completion notifications.
**What**: Provides methods to play notification sounds when timer reaches zero.

### Styling Strategy
- **CSS Modules**: Used for component-specific styling to avoid conflicts
- **Global Styles**: Base typography, colors, and responsive design utilities
- **Mobile-First**: Responsive design approach ensuring mobile compatibility

### State Management
- **Local State**: Using React useState and custom hooks for timer functionality
- **No External State Library**: The application is simple enough to not require Redux or similar libraries

### File Structure Rationale
```
src/
├── components/
│   ├── common/          # Shared components across features
│   └── ui/              # Reusable UI components
├── features/
│   └── timer/           # Timer-specific components and logic
├── hooks/               # Custom React hooks
├── styles/              # Global styles and CSS utilities
├── utils/               # Utility functions
└── assets/              # Static assets (sounds, images)
```

This structure promotes:
- **Modularity**: Each component has a single responsibility
- **Reusability**: UI components can be reused across different features
- **Testability**: Logic is separated from presentation
- **Maintainability**: Clear separation of concerns

## Development Guidelines
- Follow React functional components with hooks
- Use TypeScript for type safety
- Implement responsive design for mobile compatibility
- Use semantic HTML for accessibility
- Follow the established naming conventions (PascalCase for components, camelCase for functions)

## Getting Started
1. Install dependencies: `npm install`
2. Start development server: `npm run dev`
3. Build for production: `npm run build`

## Future Enhancements
- Add preset timer options (5min, 10min, etc.)
- Implement timer history
- Add custom notification sounds
- Support for multiple simultaneous timers

