import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Sora", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
        xl: "calc(var(--radius) + 4px)",
        "2xl": "calc(var(--radius) + 8px)",
      },
      colors: {
        ink: "#0C0E1A",
        paper: "#F6F5F1",
        iris: "#5145E5",
        signal: "#FF5C38",
        mist: "#E5E3DC",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        border: "hsl(var(--border))",
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
        },
      },
      boxShadow: {
        neu: "var(--shadow-neu)",
        "neu-sm": "var(--shadow-neu-sm)",
        "neu-lg": "var(--shadow-neu-lg)",
        "neu-inset": "var(--shadow-neu-inset)",
      },
      keyframes: {
        "assemble-in": {
          "0%": { opacity: "0", transform: "translateY(14px) rotate(var(--tilt, 0deg))" },
          "100%": { opacity: "1", transform: "translateY(0) rotate(var(--tilt, 0deg))" },
        },
        drift: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
      animation: {
        "assemble-in": "assemble-in 0.7s cubic-bezier(0.22,1,0.36,1) both",
        drift: "drift 6s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
