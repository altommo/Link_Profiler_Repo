/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // NASA Mission Control Aesthetic Color Palette
        'nasa-dark-blue': '#0A0A1A', // Deepest background, almost black with a hint of blue/purple
        'nasa-medium-blue': '#1A1A3A', // Slightly lighter background for panels, forms, etc.
        'nasa-light-gray': '#E0E0E0', // Primary text color for readability
        'nasa-cyan': '#00FFFF', // Electric blue/cyan for primary accents, titles, active states
        'nasa-amber': '#FFBF00', // Amber for warnings, highlights, secondary accents
        'nasa-red': '#FF0000', // Bright red for critical alerts, errors, danger actions
        'nasa-green': '#00FF00', // Bright green for success, active status
        'nasa-blue': '#007BFF', // General purpose blue, e.g., for links or less critical elements
      },
      fontFamily: {
        mono: ['"Space Mono"', 'monospace'], // A monospace font for data displays
        sans: ['"Inter"', 'sans-serif'], // A clean sans-serif for general text
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 5px rgba(0, 255, 255, 0.5), 0 0 10px rgba(0, 255, 255, 0.3)' },
          '50%': { boxShadow: '0 0 10px rgba(0, 255, 255, 0.8), 0 0 20px rgba(0, 255, 255, 0.6)' },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2s infinite ease-in-out',
      },
    },
  },
  plugins: [],
}
