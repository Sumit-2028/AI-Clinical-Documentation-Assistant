/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        parchment: '#F5EFE4', beige: '#EDE3D3', paper: '#FCF9F3', ivory: '#FFFDF8',
        ink: '#44372F', secondary: '#75685C', muted: '#A69A8D', border: '#DDD2C2',
        teal: '#176B67', 'teal-hover': '#125A57', 'accent-teal': '#2A8C86', 'soft-teal': '#DCECE7',
        verified: '#3F8F72', review: '#C4874A', 'high-risk': '#B85450', information: '#527FA3',
      },
      fontFamily: { display: ['Manrope', 'sans-serif'], sans: ['Inter', 'sans-serif'] },
      boxShadow: { card: '0 12px 34px rgba(68, 55, 47, 0.06)', float: '0 20px 45px rgba(68, 55, 47, 0.1)' },
    },
  },
  plugins: [],
}
