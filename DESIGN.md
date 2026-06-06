---
name: Professional Career Engine
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#001a42'
  on-tertiary-container: '#3980f4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#d8e2ff'
  tertiary-fixed-dim: '#adc6ff'
  on-tertiary-fixed: '#001a42'
  on-tertiary-fixed-variant: '#004395'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 48px
  container-max: 1280px
---

## Brand & Style

The design system is engineered for the high-stakes environment of career development. It prioritizes **clarity, efficiency, and trust** to reduce the cognitive load on candidates navigating complex application processes. 

The aesthetic is **Modern Corporate**, leaning into **Minimalism**. By utilizing generous whitespace and a disciplined color palette, we ensure the user's focus remains entirely on the content—job offers and application statuses. The interface should feel like a premium productivity tool: reliable, fast, and sophisticated. Every interaction is designed to evoke a sense of progress and professional readiness.

## Colors

The palette is anchored by a **Deep Navy (Primary)**, chosen to project authority and institutional trust. This is balanced by a high-contrast **Success Green (Secondary)**, which is reserved exclusively for "positive" actions: successful submissions, "Open" status badges, and validation states. 

**White** is the structural foundation, used for all primary surfaces to maintain a clean, airy feel. A **Light Slate (Neutral)** is utilized for borders and secondary text to ensure hierarchy without adding visual noise. A bright **Action Blue (Tertiary)** is used sparingly for interactive links and focus states to differentiate them from static brand elements.

## Typography

This design system uses **Inter** exclusively. It is a typeface designed for screens, offering exceptional legibility at small sizes—crucial for mobile job browsing. 

- **Headlines:** Use Bold weights with tight letter-spacing to create a strong, "editorial" feel for section headers.
- **Body:** Standardized at 16px for optimal readability across all devices. 
- **Labels:** Used for badges, categories, and overlines. We use a Medium/Semi-bold weight and occasional uppercase styling to distinguish metadata from content.

## Layout & Spacing

We employ a **12-column Fluid Grid** for desktop, transitioning to a **single-column stack** for mobile devices. The rhythm is based on a **4px base unit**.

- **Margins:** 16px on mobile to maximize screen real estate; 48px on desktop to provide breathing room.
- **Vertical Rhythm:** Components are separated by increments of 8px (e.g., 24px between cards, 48px between sections).
- **Safe Areas:** Forms and content blocks should never touch the edge of the screen, maintaining a protective "inner padding" of at least 24px within all container elements.

## Elevation & Depth

To maintain a "Modern Professional" feel, this design system avoids heavy shadows. Instead, it uses **Tonal Layering** and **Soft Ambient Shadows**.

- **Level 0 (Background):** Pure white or ultra-light grey (#F8FAFC).
- **Level 1 (Cards/Inputs):** White surface with a 1px border (#E2E8F0).
- **Level 2 (Hover/Active):** A very soft, diffused shadow (0px 4px 12px rgba(15, 23, 42, 0.05)) to indicate interactivity.
- **Level 3 (Modals/Popovers):** Higher contrast shadow to separate the element from the page logic.

Depth is used functionally: higher elevation always indicates that an element is temporary or requires immediate attention.

## Shapes

The shape language is **Soft (0.25rem / 4px)**. This choice strikes a balance between the "rigidity" of traditional corporate software and the "friendliness" of consumer apps.

- **Standard Buttons & Inputs:** 4px radius.
- **Offer Cards:** 8px (rounded-lg) to create a distinct container.
- **Status Badges:** Fully rounded (pill-shaped) to differentiate them from clickable rectangular buttons.

## Components

### Offer Cards
Cards are the primary vehicle for information. They must feature:
- A clear **1-pixel border** (Level 1 elevation).
- The company logo in a 48x48px container.
- Title in `headline-md`, Secondary info (location/salary) in `body-md`.
- A "Save" icon button in the top-right corner.

### Status Badges
Used for application tracking (e.g., "Sent", "Interview", "Accepted").
- **Success:** Green background (10% opacity) with Green text.
- **Pending:** Blue background (10% opacity) with Blue text.
- **Neutral:** Slate background (10% opacity) with Slate text.

### Search Forms
Simplified to the core. A horizontal bar on desktop, stacked on mobile.
- **Inputs:** Use a 1px border that turns `Tertiary Blue` on focus.
- **Primary CTA:** Deep Navy background with White text for maximum "clickability" and visual weight.

### Buttons
- **Primary:** Navy background, white text. Bold and authoritative.
- **Secondary:** White background, Navy border, Navy text.
- **Ghost:** No border/background. Used for low-priority actions like "Cancel" or "Clear Filters."

### Lists
Candidate lists or job requirements should use custom **Green checkmark bullets** to reinforce the "Success" brand pillar.