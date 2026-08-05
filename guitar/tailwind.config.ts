import type { Config } from 'tailwindcss';

export default {
  content: ['./src/main/frontend/index.html', './src/main/frontend/src/**/*.{ts,tsx}'],
  theme: {
    extend: {}
  },
  plugins: []
} satisfies Config;
