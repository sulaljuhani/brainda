# Brainda UI Color Guide

This document provides a comprehensive overview of all colors used in the Brainda application UI.

## Color System Overview

Brainda uses a unified dark theme with a monochromatic, flat design aesthetic. All colors are defined as CSS custom properties (variables) for consistency and easy theming.

---

## Background Colors

### Primary Backgrounds
| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--bg-primary` | `#212121` | **Main background color** - All pages, containers, surfaces |
| `--bg-secondary` | `#212121` | Sidebar, body, main content (same as bg-primary for consistency) |
| `--bg-tertiary` | `#2f2f2f` | Hover states, active states, subtle backgrounds |
| `--bg-elevated` | `#212121` | Message bubbles, chat input box (same as bg-primary) |
| `--bg-user-message` | `#212121` | User message bubbles |
| `--bg-input` | `#303030` | Input boxes, text areas, form fields |

### Usage Examples
- **Sidebar**: `#212121` (--bg-secondary)
- **Main content area**: `#212121` (--bg-primary)
- **Chat input box**: `#303030` (--bg-input)
- **Message bubbles**: `#212121` (--bg-elevated)
- **Hover effects**: `#2f2f2f` (--bg-tertiary)
- **Active navigation items**: `#2f2f2f` (--bg-tertiary)

---

## Text Colors

| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--text-primary` | `#f5fcfe` | Main text, headings, labels, active elements |
| `--text-secondary` | `#818181` | Secondary text, metadata, navigation items, icons |
| `--text-tertiary` | `#818181` | Subtle text, placeholders, disabled states |
| `--text-inverse` | `#1a1a1a` | Text on light backgrounds (rare) |

### Usage Examples
- **Navigation labels**: `#818181` (--text-secondary)
- **Active navigation**: `#f5fcfe` (--text-primary)
- **Input placeholders**: `#818181` (--text-tertiary)
- **Button text**: `#f5fcfe` (--text-primary)
- **Icons**: `#818181` (--text-secondary)

---

## Accent Colors

### Primary Accent (Monochromatic)
| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--accent-primary` | `#f5fcfe` | Mapped to text-primary for monochromatic design |
| `--accent-hover` | `#2f2f2f` | Button hover state background |
| `--accent-active` | `#2f2f2f` | Active/pressed state |
| `--accent-soft` | `#2f2f2f` | Muted accent for subtle highlights |

### Usage Examples
- **Button hover**: `#2f2f2f` (--accent-hover)
- **Profile avatar**: `#f5fcfe` background (--text-primary)
- **Active indicators**: `#2f2f2f` (--bg-tertiary)
- **Interactive elements**: Transparent background with `#2f2f2f` on hover

---

## Border Colors

| Variable | Hex Code | Usage | Notes |
|----------|----------|-------|-------|
| `--border-subtle` | `#2f2f2f` | Dividers, subtle borders | Unified with hover state |
| `--border-default` | `#2f2f2f` | Default borders | Minimal contrast with background |
| `--border-strong` | `#2f2f2f` | Strong borders | Same as default for consistency |

### Design Philosophy
Borders are intentionally **very subtle** and unified at `#2f2f2f` for a clean, minimalist appearance. This creates visual separation without harsh lines, maintaining the flat, monochromatic aesthetic.

### Usage Examples
- **Sidebar border**: `#2f2f2f` (--border-default)
- **Message bubble border**: `#2f2f2f` (--border-default)
- **Input borders**: `#2f2f2f` (--border-default)
- **Divider lines**: `#2f2f2f` (--border-subtle)
- **Most borders are removed** in favor of transparent backgrounds with hover states

---

## Semantic Colors

### Status Colors (Monochromatic)
| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--success` | `#f5fcfe` | Mapped to text-primary (removed green) |
| `--warning` | `#818181` | Mapped to text-secondary (removed orange) |
| `--error` | `#ef4444` | Error messages (kept for critical warnings only) |
| `--info` | `#818181` | Mapped to text-secondary (removed blue) |

### Usage Examples
- **All semantic colors now use monochromatic palette**
- **Error red (#ef4444) kept only for critical system errors**
- **Most UI elements use transparent/hover pattern instead of semantic colors**

---

## Special Purpose Colors

### Unified Theme Tokens
| Variable | Hex Code | Usage |
|----------|----------|-------|
| `--chatgpt-sidebar-hover` | `#2f2f2f` | Sidebar navigation hover state (updated) |
| `--chatgpt-code-bg` | `#212121` | Code block backgrounds (same as bg-primary) |
| `--chatgpt-scrollbar-thumb` | `#2f2f2f` | Scrollbar styling (updated) |
| `--chatgpt-chip-bg` | `#212121` | Chip/tag backgrounds (same as bg-primary) |
| `--chatgpt-chip-border` | `#2f2f2f` | Chip/tag borders (updated) |

---

## Legacy/Compatibility Colors

These colors are maintained for backward compatibility but rarely used:

| Variable | Hex Code | Original Purpose |
|----------|----------|------------------|
| `--color-primary` | `#10A37F` | Legacy primary color |
| `--color-primary-dark` | `#0E8C6D` | Legacy primary dark |
| `--color-danger` | `#dc2626` | Legacy danger color |
| `--color-danger-dark` | `#b91c1c` | Legacy danger dark |

Gray scale variables (`--color-gray-50` through `--color-gray-900`) are also defined but primarily used in legacy components.

---

## Border Radius Values

| Variable | Value | Usage |
|----------|-------|-------|
| `--radius-sm` | `6px` | Small elements, icons, buttons |
| `--radius-md` | `8px` | Standard inputs, cards |
| `--radius-lg` | `12px` | Large cards, modals |
| `--radius-xl` | `16px` | Extra large containers |
| `--radius-full` | `9999px` | Circular elements (avatars) |
| `--radius-chatgpt-input` | `12px` | Chat input box |
| `--radius-chatgpt-bubble` | `8px` | Message bubbles |
| `--radius-chatgpt-card` | `8px` | Card components |

---

## Shadow Values

| Variable | Value | Usage |
|----------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0, 0, 0, 0.05)` | Small shadows |
| `--shadow-md` | `0 4px 6px -1px rgba(0, 0, 0, 0.1)` | Medium shadows |
| `--shadow-lg` | `0 10px 15px -3px rgba(0, 0, 0, 0.1)` | Large shadows |
| `--shadow-xl` | `0 20px 25px -5px rgba(0, 0, 0, 0.1)` | Extra large shadows |
| `--shadow-chatgpt-soft` | `0 2px 8px rgba(0, 0, 0, 0.15)` | Soft ChatGPT-style shadow |

---

## Color Usage Guidelines

### 1. Background Hierarchy
- **Base**: Use `#212121` for all main backgrounds (unified)
- **Elevated**: Use `#212121` - no elevation difference, flat design
- **Interactive**: Use `#2f2f2f` for hover and active states
- **Input fields**: Use `#303030` for text inputs and form fields

### 2. Text Hierarchy
- **Primary**: Use `#f5fcfe` for important text, headings, active states
- **Secondary**: Use `#818181` for supporting text, icons, navigation
- **Tertiary**: Use `#818181` - same as secondary for simplicity

### 3. Borders
- **Unified at `#2f2f2f`** - minimal contrast with background
- **Most borders removed** - prefer transparent backgrounds
- Use borders only when absolutely necessary for visual separation
- Borders should never be a prominent visual element

### 4. Interactive Elements
- **Default state**: Transparent background, `#818181` text/icons
- **Hover state**: `#2f2f2f` background, `#f5fcfe` text
- **Active state**: `#2f2f2f` background
- **No colored accents** - pure monochromatic design

### 5. Button Design
- **All buttons**: Transparent background with no borders
- **Hover**: `#2f2f2f` background
- **Disabled**: Transparent background, reduced opacity
- **No green, orange, or blue colors** anywhere in the UI

### 6. Monochromatic Design Philosophy
- Favor subtle variations in background color over borders
- Use background color changes for interaction feedback
- Keep contrast minimal for a cohesive, calm interface
- No colored accents except critical error red (#ef4444)

---

## Color Accessibility

### Contrast Ratios
The unified monochromatic design maintains good accessibility:
- Primary text (#f5fcfe) on background (#212121): ~15:1 (excellent)
- Secondary text (#818181) on background (#212121): ~4.5:1 (adequate for large text)
- Hover state (#2f2f2f) vs background (#212121): Subtle but perceivable

### Border Visibility
Borders are **extremely subtle** by design:
- Border (#2f2f2f) vs background (#212121): ~1.2:1 contrast
- This creates visual separation without harsh lines
- Accessibility maintained through hover states and spacing

---

## Dark Theme Only

Brainda uses a **unified dark theme only**. All colors are optimized for dark mode viewing and low-light environments.

---

## Unified Color Palette Summary

The entire application uses only **5 colors**:

1. **#212121** - All backgrounds (main, sidebar, elevated surfaces)
2. **#303030** - Input boxes only
3. **#2f2f2f** - Borders, hover states, active states, dividers
4. **#f5fcfe** - Primary text, active elements, important content
5. **#818181** - Secondary text, icons, placeholders

**Plus one exception:**
- **#ef4444** - Critical error messages only (rarely used)

This creates a **pure monochromatic, flat design** with no green, orange, or blue colors.

---

## Color Modification Notes

When modifying colors:
1. Update values in `/app/web/src/styles/global.css`
2. All color variables are defined in the `:root` selector
3. Changes propagate automatically throughout the application
4. **Maintain the monochromatic palette** - no colored accents
5. Test all interactive states (hover, active, disabled)
6. Verify text remains readable against all backgrounds
7. Update this guide when making changes

---

## File Locations

- **Color Definitions**: `app/web/src/styles/global.css`
- **Component Styles**: Use CSS variables when possible
- **Hardcoded colors**: Used in some components for direct `#2f2f2f` hover states
- **Button pattern**: All buttons use transparent background, `#2f2f2f` on hover

---

*Last Updated: 2025-01-16 (Unified Monochromatic Palette)*
