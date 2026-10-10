import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'InfraLink Field Operations',
    short_name: 'InfraLink Field',
    description: 'Offline field updates for public works.',
    start_url: '/field',
    scope: '/field',
    display: 'standalone',
    background_color: '#f8fafc',
    theme_color: '#075e67',
    icons: [{ src: '/field-icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
  };
}
