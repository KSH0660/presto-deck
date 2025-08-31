/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './*.html',
    '../app/web/templates/**/*.html',
  ],
  theme: {
    extend: {},
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
