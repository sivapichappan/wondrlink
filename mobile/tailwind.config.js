/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
  ],
  presets: [require("nativewind/preset")],
  theme: {
    extend: {
      colors: {
        primary: "#1F5D4F",
        "primary-light": "#2A7869",
        accent: "#E89260",
        surface: "#FFFFFF",
        "surface-muted": "#F7F7F5",
        "sidebar-bg": "#EDF2EF",
        border: "#E1E4E1",
        "text-primary": "#0F201C",
        "text-secondary": "#475554",
        "text-muted": "#6F7B7A",
        danger: "#B3261E",
      },
      fontFamily: {
        sans: ["Geist", "System"],
        serif: ["Fraunces", "Georgia", "serif"],
      },
      borderRadius: {
        sm: "8px",
        md: "12px",
        lg: "16px",
        xl: "20px",
      },
    },
  },
  plugins: [],
};
