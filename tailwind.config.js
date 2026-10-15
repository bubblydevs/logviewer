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
      // Matches help.shopjava.uk (dark theme).
      colors: {
        page: "#0f0f11",
        card: "#17171a",
        raised: "#1f1f23",
        line: "#2a2a2e",
        muted: "#a1a1aa",
      },
      fontFamily: {
        sans: ["Poppins", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
};
