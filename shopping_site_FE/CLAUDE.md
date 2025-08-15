# CLAUDE.md - Shopping Site Frontend Development Guide

## Project Overview

This is a modern e-commerce frontend application built with React, TypeScript, and Vite. The application follows a feature-based architecture to ensure scalability and maintainability.

## Architecture Decisions

### Why Feature-Based Architecture?

The project is organized around features rather than technical layers to:
- **Improve Maintainability**: Related code is co-located, making it easier to understand and modify
- **Enable Team Scalability**: Different teams can work on different features with minimal conflicts
- **Facilitate Code Reuse**: Common components are separated from feature-specific logic
- **Support Incremental Development**: Features can be developed and deployed independently

### What Components Were Created?

#### Core Directory Structure:

1. **`src/components/`** - Shared, reusable components
   - `common/` - Business-agnostic components (Button, Modal, etc.)
   - `ui/` - UI-specific components (Header, Footer, Navigation)

2. **`src/features/`** - Feature-specific modules
   - `products/` - Product listing, detail, and related functionality
   - `cart/` - Shopping cart management and checkout flow
   - `search/` - Search functionality and filters

3. **`src/hooks/`** - Custom React hooks for shared logic
4. **`src/services/`** - API clients and external service integrations
5. **`src/store/`** - Global state management (Redux/Zustand)
6. **`src/styles/`** - Global styles and theme configuration
7. **`src/utils/`** - Pure utility functions and helpers

### Why This Structure?

**Scalability**: As the application grows, new features can be added without affecting existing code. Each feature module is self-contained with its own components, hooks, and services.

**Maintainability**: Developers can quickly locate code related to specific functionality. The separation of concerns makes debugging and testing easier.

**Reusability**: Common components in the `components/` directory can be used across multiple features, reducing code duplication.

**Team Collaboration**: Multiple developers can work on different features simultaneously with minimal merge conflicts.

## Development Guidelines

### Component Creation Rules

1. **Functional Components Only**: Use functional components with hooks
2. **TypeScript First**: All components must have proper TypeScript interfaces
3. **Single Responsibility**: Each component should have one clear purpose
4. **Props Interface**: Define clear interfaces for component props

### State Management Strategy

1. **Local State First**: Use `useState` for component-specific state
2. **Lift State Up**: Move state to common ancestor when shared between components
3. **Global State**: Use Redux Toolkit or Zustand for application-wide state

### File Naming Conventions

- Components: `PascalCase.tsx` (e.g., `ProductCard.tsx`)
- Hooks: `camelCase.ts` starting with "use" (e.g., `useProductSearch.ts`)
- Services: `camelCase.ts` (e.g., `productApi.ts`)
- Utils: `camelCase.ts` (e.g., `formatPrice.ts`)

### Import Organization

```typescript
// External libraries
import React from "react";
import { useState, useEffect } from "react";

// Internal components
import { Button } from "../components/ui/Button";
import { ProductCard } from "../features/products/ProductCard";

// Hooks and services
import { useProductSearch } from "../hooks/useProductSearch";
import { productApi } from "../services/productApi";

// Types
import type { Product } from "../types/product";
```

### Error Handling

1. **Error Boundaries**: Implement at feature level to catch and handle errors gracefully
2. **Loading States**: Always provide loading indicators for async operations
3. **Empty States**: Handle empty data scenarios with meaningful messages

### Performance Considerations

1. **Code Splitting**: Use React.lazy() for route-based code splitting
2. **Memoization**: Use React.memo, useMemo, and useCallback appropriately
3. **Bundle Analysis**: Regularly analyze bundle size and optimize imports

## Next Steps for Development

1. **Set up routing** with React Router DOM for navigation between pages
2. **Implement global state management** for cart and user session
3. **Create base UI components** (Button, Input, Card, etc.)
4. **Develop product-related features** (search, filtering, detail view)
5. **Add responsive design** with CSS modules or styled-components
6. **Implement error boundaries** and loading states
7. **Add unit tests** with React Testing Library

## API Integration

Since this is a frontend-only application, consider:
- Using mock data during development
- Implementing a service layer that can easily switch between mock and real APIs
- Creating TypeScript interfaces for all API responses
- Implementing proper error handling for network requests

This architecture provides a solid foundation for building a scalable, maintainable e-commerce frontend application.

