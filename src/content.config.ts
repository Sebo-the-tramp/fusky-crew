import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const crew = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/crew' }),
  schema: z.object({
    name: z.string(),
    role: z.enum(['film','support','drink','drone','lead','tbd']),
    phone: z.string().optional(),
    color: z.string().default('#ff5a36'),
    priority: z.number().default(10),
    equipment: z.array(z.string()).default([])
  })
});

export const collections = { crew };
