# React Development Standards

## Component Structure
- Use functional components with hooks
- Export default at the bottom of the file
- Import React at the top: `import React from 'react';`
- Use descriptive component names in PascalCase

## Hooks Usage
- Use `useState` for local component state
- Use `useEffect` for side effects and cleanup
- Use `useRef` for DOM references and mutable values
- Always include dependency arrays in useEffect

## Code Style
- Use arrow functions for event handlers
- Use template literals for string interpolation
- Use destructuring for props and state
- Keep components focused on a single responsibility

## State Management
- Keep state as close to where it's used as possible
- Use controlled components for form inputs
- Lift state up when multiple components need the same data
- Use callback functions to update parent state

## Performance
- Use React.memo for expensive components
- Use useMemo for expensive calculations
- Use useCallback for stable function references
- Avoid creating objects/arrays in render

## Example Pattern
```jsx
import React, { useState, useEffect, useRef } from 'react';

function MyComponent({ prop1, prop2 }) {
  const [state, setState] = useState(initialValue);
  const ref = useRef(null);

  useEffect(() => {
    // Side effect
    return () => {
      // Cleanup
    };
  }, [dependencies]);

  const handleClick = () => {
    setState(newValue);
  };

  return (
    <div>
      {/* JSX content */}
    </div>
  );
}

export default MyComponent;
```


# Material-UI Development Guidelines

## Import Patterns
- Import specific components: `import { Button, TextField } from '@mui/material';`
- Import icons: `import { PlayArrow } from '@mui/icons-material';`
- Import emotion for styled components: `import { styled } from '@mui/material/styles';`

## Component Usage
- Use Material-UI components when available instead of HTML elements
- Prefer `Button` over `<button>`
- Use `TextField` for form inputs
- Use `Box` for layout containers
- Use `Typography` for text styling

## Styling Approaches
1. **sx prop** for simple styles:
   ```jsx
   <Box sx={{ padding: 2, margin: 1 }}>
   ```

2. **styled() function** for reusable components:
   ```jsx
   const StyledButton = styled(Button)(({ theme }) => ({
     backgroundColor: theme.palette.primary.main,
   }));
   ```

3. **Inline styles** for dynamic styling (as used in timeboxTimer):
   ```jsx
   <div style={{ background: isActive ? '#fff' : '#f0f0f0' }}>
   ```

## Accessibility
- Use proper ARIA labels
- Ensure keyboard navigation works
- Use semantic HTML elements
- Provide alt text for images

## Performance
- Import only what you need
- Use dynamic imports for large components
- Consider bundle size impact

# ESLint Compliance Guidelines

## Key Rules to Follow

### Variable Naming
- Use camelCase for variables and functions
- Use PascalCase for components and constructors
- Constants in UPPER_SNAKE_CASE are allowed (varsIgnorePattern: '^[A-Z_]')

### React Hooks Rules
- Call hooks only at the top level of functions
- Don't call hooks inside loops, conditions, or nested functions
- Use `useEffect` dependencies correctly
- Follow rules of hooks consistently

### React Refresh Rules
- Export components as default exports
- Ensure fast refresh works properly
- Avoid exporting non-component functions from component files

### Code Quality
- Remove unused variables (except those matching `^[A-Z_]` pattern)
- Use consistent indentation
- Prefer `const` over `let` when possible
- Use template literals for string concatenation

## Running ESLint
```bash
npm run lint          # Check for linting errors
npm run lint -- --fix # Auto-fix fixable errors
```

## Common Patterns to Avoid
```javascript
// ❌ Bad
let unused = 'value';
function MyComponent() {
  if (condition) {
    useEffect(() => {}, []); // Hooks in conditions
  }
}

// ✅ Good
const MY_CONSTANT = 'value'; // Uppercase constant
function MyComponent() {
  useEffect(() => {
    if (condition) {
      // Logic inside effect
    }
  }, [condition]);
}
```

## Core Principles
- **Utility-first approach**: Build designs using utility classes
- **Responsive design**: Use responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`)
- **Consistency**: Use Tailwind's design tokens for spacing, colors, and sizing
