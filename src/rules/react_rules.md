# React Development Guide and Conventions

This document outlines the best practices and conventions for developing applications with React. Following these guidelines will help ensure that your projects are robust, maintainable, and scalable.

## 1. Project Structure

A well-organized project structure is crucial for maintainability. While Create React App provides a default layout, the following structure is highly recommended for scalability.

### 1.1. Directory Layout

Organize your code into feature-specific or domain-specific directories. This approach enhances modularity and makes the codebase easier to navigate.

```
src/
├── assets/         // Static assets like images, fonts
├── components/     // Reusable, shared components
│   ├── common/
│   └── ui/
├── features/       // Feature-specific modules
│   ├── authentication/
│   │   ├── AuthForm.js
│   │   └── authSlice.js
│   └── products/
│       ├── ProductList.js
│       └── productAPI.js
├── hooks/          // Custom hooks
├── services/       // API clients, external services
├── store/          // State management (e.g., Redux)
├── styles/         // Global styles
└── utils/          // Utility functions
```

In this structure:

- **`components`**: Contains globally reusable components (e.g., `Button`, `Modal`).
- **`features`**: Each feature module contains its own components, state logic, and services.
- **`services`**: Manages communication with external APIs.
- **`store`**: Centralized state management configuration.

### 1.2. Naming Conventions

- **Components**: Use `PascalCase` (e.g., `UserProfile.js`).
- **Files/Folders**: Use `camelCase` or `kebab-case` for non-component files (e.g., `apiClient.js`, `auth-utils`).
- **Functions/Variables**: Use `camelCase` (e.g., `fetchUserData`).

## 2. Component Design

Adhere to modern React practices for creating clean, efficient, and reusable components.

### 2.1. Functional Components and Hooks

- **Functional Components**: Exclusively use functional components with hooks over class-based components.
- **`useState`**: For managing local component state.
- **`useEffect`**: For handling side effects like data fetching or subscriptions. Always include a dependency array to prevent infinite loops.
- **`useCallback` and `useMemo`**: To memoize functions and values, optimizing performance by preventing unnecessary re-renders.

### 2.2. State Management

- **Local State First**: Keep state as close as possible to where it is used.
- **Lift State Up**: When multiple components need access to the same state, lift it to their closest common ancestor.
- **Global State**: For complex, application-wide state, use a dedicated state management library like Redux with Redux Toolkit.

## 3. Dependency Management and Conflict Resolution

Effective dependency management with `npm` is critical for a stable React project. This section provides a comprehensive guide to resolving common `peerDependency` conflicts without resorting to the `--legacy-peer-deps` flag.

### 3.1. Understanding `peerDependencies`

`peerDependencies` is a field in `package.json` where a package specifies its compatibility with a host package version. For a React component library, `react` and `react-dom` are typical `peerDependencies`.

Since npm v7, `peerDependencies` are installed automatically. If a version conflict is detected in the dependency tree, npm will abort the installation, which is a common source of installation failures.

### 3.2. Why You Should Avoid `--legacy-peer-deps`

The `--legacy-peer-deps` flag makes npm ignore `peerDependency` conflicts, similar to older npm versions. While it seems like a quick fix, it can lead to:

- **Runtime Errors**: Using incompatible versions of libraries (e.g., React) can cause unpredictable errors.
- **Hidden Issues**: It masks underlying dependency tree problems that should be properly resolved.

It is highly recommended to resolve these conflicts directly.

### 3.3. Steps to Resolve Dependency Conflicts

1.  **Analyze the npm Error Message**: The error output from `npm install` will tell you which packages have conflicting `peerDependency` requirements.
2.  **Inspect the Dependency Tree**: Use `npm ls [package-name]` (e.g., `npm ls react`) to see which versions are required by different packages.
3.  **Adjust Package Versions**: Update or downgrade packages to align their `peerDependency` requirements.
4.  **Use `overrides`**: As a last resort, use the `overrides` field in `package.json` to force a specific version of a package throughout your project. This is especially useful for ensuring a single version of `react` and `react-dom`.

    ```json
    // package.json
    "overrides": {
      "react": "^18.2.0",
      "react-dom": "^18.2.0"
    }
    ```

### 3.4. Best Practices

- **UI Libraries**: When using libraries like Material-UI or Ant Design, import components directly to minimize the final bundle size.
- **Bundle Size Audits**: Regularly audit your bundle size with tools like `source-map-explorer` to identify and remove unnecessary dependencies.

## 4. Styling

Adopt a consistent styling strategy across the application.

- **CSS-in-JS**: Libraries like `styled-components` or `Emotion` provide scoped, dynamic, and maintainable styles.
- **Utility-First CSS**: Frameworks like Tailwind CSS allow for rapid UI development with a consistent design system.
- **Global Styles**: Use a global stylesheet for base styles, typography, and CSS resets.

## 5. Exception Handling

Implement a clear strategy for handling errors to create a resilient user experience.

- **Error Boundaries**: Use React's Error Boundaries to catch JavaScript errors in component trees, log them, and display a fallback UI.
- **Network Errors**: Gracefully handle failed API requests by displaying user-friendly messages and providing retry options.

## 6. Testing

A comprehensive testing strategy is essential for building reliable applications.

- **Unit Tests**: Test individual components and functions in isolation using frameworks like Jest and React Testing Library.
- **Integration Tests**: Test the interaction between multiple components to ensure they work together as expected.
- **End-to-End Tests**: Use tools like Cypress or Playwright to test complete user flows from the UI to the backend.

## 7. Security

Secure your application against common web vulnerabilities.

- **XSS Prevention**: React automatically escapes content rendered in JSX, providing protection against Cross-Site Scripting (XSS). Avoid dangerous practices like using `dangerouslySetInnerHTML`.
- **Data Handling**: Ensure sensitive data is handled securely on the client-side and transmitted over HTTPS.
- **Dependency Audits**: Regularly run `npm audit` or `yarn audit` to identify and patch vulnerabilities in third-party packages.

By adhering to these guidelines and consulting the [official React documentation](https://react.dev/), you can develop high-quality React applications that are easy to maintain and scale.
