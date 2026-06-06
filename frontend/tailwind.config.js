/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        theater: {
          bg: '#ffffff',
          card: '#f7f7f6',
          border: '#ebebea',
          accent: '#111111',
          'accent-light': '#3f3f3f',
          blue: '#2563eb',
          red: '#dc2626',
          green: '#16a34a',
          gray: '#5f5f5f',
          muted: '#a1a1a1',
          text: '#111111',
          'text-secondary': '#5f5f5f',
        }
      },

      fontFamily: {
        sans: ['Inter', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },

      letterSpacing: {
        tighterest: '-0.06em',
      },

      backgroundImage: {
        'grid-pattern':
          "linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px)",
      },

      backgroundSize: {
        grid: '24px 24px',
      }
    },
  },
  plugins: [],
}
