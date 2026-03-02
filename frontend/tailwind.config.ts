import type { Config } from 'tailwindcss'
import typography from '@tailwindcss/typography'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        drs: {
          bg:             '#0A0B0F',
          s1:             '#111318',
          s2:             '#1A1D27',
          s3:             '#242736',
          border:         '#2A2D3A',
          'border-bright':'#3D4155',
          text:           '#F0F1F6',
          muted:          '#8B8FA8',
          faint:          '#50536A',
          accent:         '#7C8CFF',
          green:          '#22C55E',
          yellow:         '#EAB308',
          red:            '#EF4444',
          orange:         '#F97316',
          // Agent node colors
          'node-writer':    '#4F6EF7',
          'node-jury':      '#A855F7',
          'node-research':  '#06B6D4',
          'node-reflect':   '#F97316',
          'node-style':     '#EC4899',
          'node-coherence': '#22C55E',
          'node-publish':   '#EAB308',
          'node-shine':     '#14B8A6',
          'node-rlm':       '#818CF8',
        },
      },
      fontFamily: {
        sans: ['Inter var', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [typography],
}

export default config
