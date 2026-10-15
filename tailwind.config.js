/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html"],
  corePlugins: {
    // The log page still uses Materialize, so Tailwind's global reset is replaced
    // by a scoped one in tailwind.src.css (applies inside .tw only).
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#5865F2",
          600: "#4752C4",
        },
        surface: {
          950: "#0e0f11",
          900: "#16171a",
          800: "#1e1f22",
          700: "#2b2d31",
          600: "#3a3c42",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
};
