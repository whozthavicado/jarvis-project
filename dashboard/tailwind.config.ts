import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        zero: {
          bgFrom: "#05070C",
          bgTo: "#0A0E16",
          accent: "#2E9BFF",
          accentLight: "#5AC8FF",
          surface: "#0D1420",
          border: "rgba(255,255,255,0.08)",
          text: {
            primary: "#FFFFFF",
            muted: "#7C8BA6",
          },
        },
      },
      borderRadius: {
        zero: "18px",
      },
    },
  },
  plugins: [],
};

export default config;
