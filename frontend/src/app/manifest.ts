import { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Smart Diary',
    short_name: 'Diary',
    description: 'An intelligent diary with LLM insights',
    start_url: '/',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#8b5cf6',
    categories: ['productivity', 'health', 'lifestyle'],
    icons: [
      {
        src: '/icon-192x192.png',
        sizes: '192x192',
        type: 'image/png',
      },
      {
        src: '/icon-512x512.png',
        sizes: '512x512',
        type: 'image/png',
      },
    ],
  }
}
