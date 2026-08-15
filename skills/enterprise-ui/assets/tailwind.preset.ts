import type { Config } from "tailwindcss";

/**
 * enterprise-ui Tailwind preset.
 * Maps utilities onto the CSS custom properties defined in assets/tokens.css.
 * Usage: import this preset in tailwind.config.ts and import "tokens.css" globally.
 * Note: token colors are full color values (var()), so /opacity modifiers are not supported on them.
 */
const preset: Partial<Config> = {
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: "var(--bg-canvas)",
        surface: "var(--bg-surface)",
        subtle: "var(--bg-subtle)",
        muted: "var(--bg-muted)",
        inverse: "var(--bg-inverse)",
        border: {
          DEFAULT: "var(--border-default)",
          subtle: "var(--border-subtle)",
          strong: "var(--border-strong)",
        },
        fg: {
          DEFAULT: "var(--text-default)",
          strong: "var(--text-strong)",
          muted: "var(--text-muted)",
          subtle: "var(--text-subtle)",
          inverse: "var(--text-inverse)",
          "on-accent": "var(--text-on-accent)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          hover: "var(--accent-hover)",
          subtle: "var(--accent-subtle)",
          text: "var(--accent-text)",
        },
        success: { DEFAULT: "var(--success)", subtle: "var(--success-subtle)" },
        danger: { DEFAULT: "var(--danger)", subtle: "var(--danger-subtle)" },
        warning: { DEFAULT: "var(--warning)", subtle: "var(--warning-subtle)" },
        up: "var(--up)",
        down: "var(--down)",
      },
      borderRadius: {
        xs: "var(--radius-xs)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
      fontFamily: {
        sans: "var(--font-sans)",
        mono: "var(--font-mono)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      transitionDuration: {
        fast: "var(--duration-fast)",
        base: "var(--duration-base)",
        slow: "var(--duration-slow)",
      },
      transitionTimingFunction: {
        standard: "var(--ease-standard)",
        emphasized: "var(--ease-emphasized)",
      },
      height: { control: "var(--control-height)", row: "var(--row-height)" },
      ringColor: { DEFAULT: "var(--ring)" },
    },
  },
};

export default preset;
