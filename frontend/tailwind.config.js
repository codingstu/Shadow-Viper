/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'cyber-black': '#121212',
        'cyber-gray': '#1e1e1e',
        'cyber-green': '#42b983',
        'cyber-blue': '#00e5ff',
        'cyber-red': '#ff4444',
      },
      fontFamily: {
        mono: ['v-mono', 'Consolas', 'Monaco', 'monospace'],
      }
    },
  },
  plugins: [],
}
