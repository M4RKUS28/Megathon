/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#1f2937',
        tealcore: '#0f766e',
        signal: '#b45309',
        violetline: '#5b5bd6'
      },
      boxShadow: {
        panel: '0 1px 2px rgba(31, 41, 55, 0.08)'
      }
    }
  },
  plugins: []
}
