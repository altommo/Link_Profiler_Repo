/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'nasa-blue': '#000080', // Dark blue, reminiscent of space
        'nasa-cyan': '#00FFFF', // Bright cyan for accents
        'nasa-amber': '#FFBF00', // Amber for warnings/highlights
        'nasa-gray': '#333333', // Dark gray for panels
        'nasa-light-gray': '#555555', // Lighter gray for text
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
