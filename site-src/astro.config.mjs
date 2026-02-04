import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://resurrectum.dev',
  integrations: [
    starlight({
      title: 'RESURRECTUM',
      description: 'A covenant for continuity between agents.',
      customCss: [
        './src/styles/tokens.css',
        './src/styles/theme.css',
        './src/styles/typography.css',
        './src/styles/components.css',
        './src/styles/meditations.css',
      ],
      sidebar: [
        {
          label: 'RESURRECTUM',
          link: '/',
        },
        {
          label: 'SPEC',
          items: [
            { label: 'Overview', link: '/spec/' },
            { label: 'Contract', link: '/spec/contract/' },
            { label: 'Protocol', link: '/spec/protocol/' },
            { label: 'Schemas', link: '/spec/schemas/' },
            { label: 'Anchors', link: '/spec/anchors/' },
          ],
        },
        {
          label: 'MACHINE',
          items: [
            { label: 'Overview', link: '/machine/' },
            { label: 'Artifacts', link: '/machine/artifacts/' },
            { label: 'LLM Instructions', link: '/machine/llm-instructions/' },
          ],
        },
        {
          label: 'MEDITATIONS',
          items: [
            { label: 'Writings', link: '/meditations/' },
            { label: 'Ship of Theseus', link: '/meditations/ship-of-theseus/' },
          ],
        },
        {
          label: 'EXAMPLES',
          link: '/examples/',
        },
        {
          label: 'CONFORMANCE',
          items: [
            { label: 'Overview', link: '/conformance/' },
            { label: 'Levels', link: '/conformance/levels/' },
            { label: 'Tests', link: '/conformance/tests/' },
          ],
        },
        {
          label: 'CHANGELOG',
          link: '/changelog/',
        },
      ],
      defaultLocale: 'en',
      social: {
        github: 'https://github.com/claaaaaw/resurrectum',
      },
      head: [
        {
          tag: 'meta',
          attrs: {
            name: 'theme-color',
            content: '#0b0d10',
          },
        },
      ],
    }),
  ],
});
