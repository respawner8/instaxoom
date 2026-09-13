import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        instagram: {
          pink: "#E1306C",
          purple: "#C13584",
          orange: "#F77737",
          yellow: "#FCAF45",
        }
      },
    },
  },
  plugins: [],
};
export default config;
