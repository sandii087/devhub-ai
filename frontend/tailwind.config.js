/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#101828',
        slate: '#475467',
        canvas: '#f7f8fa',
        navy: '#101b31',
        mint: '#0e9384',
        coral: '#e85d75',
        amber: '#d97706'
      },
      boxShadow: { panel: '0 1px 2px rgba(16,24,40,.04), 0 8px 24px rgba(16,24,40,.06)' }
    }
  },
  plugins: []
}
