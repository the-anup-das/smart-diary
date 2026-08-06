import { MetadataRoute } from 'next'

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Smart Diary',
    short_name: 'Diary',
    description: 'An intelligent diary with LLM insights',
    start_url: '/',
    display: 'standalone',
    display_override: ['window-controls-overlay', 'standalone'],
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
    shortcuts: [
      {
        name: 'Write Journal',
        short_name: 'Write',
        description: 'Write a new diary entry',
        url: '/',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }]
      },
      {
        name: 'View Insights',
        short_name: 'Insights',
        description: 'View AI insights',
        url: '/insights',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }]
      },
      {
        name: 'Energy Tracker',
        short_name: 'Energy',
        description: 'Track your energy levels',
        url: '/energy',
        icons: [{ src: '/icon-192x192.png', sizes: '192x192' }]
      }
    ],
  }
}
