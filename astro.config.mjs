import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';

const [githubOwner, githubRepo] = (process.env.GITHUB_REPOSITORY ?? '/').split('/');
const site = process.env.SITE_URL
  ?? (githubOwner ? `https://${githubOwner}.github.io` : 'http://localhost:4321');
const base = process.env.BASE_PATH
  ?? (githubRepo ? (githubRepo.endsWith('.github.io') ? '/' : `/${githubRepo}`) : '/fusky-crew');

export default defineConfig({
  integrations: [mdx()],
  site,
  base,
  output: 'static'
});
