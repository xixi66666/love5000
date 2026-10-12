export function repoOgCoverUrl(owner: string, name: string): string {
  return `https://opengraph.githubassets.com/1/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`
}

export function repoAvatarUrl(owner: string, size = 600): string {
  return `https://github.com/${encodeURIComponent(owner)}.png?size=${size}`
}

export function repoFallbackCoverUrl(owner: string, name: string, width = 960, height = 560): string {
  const seed = `${owner}-${name}`.toLowerCase().replace(/[^a-z0-9-]/g, '-')
  return `https://picsum.photos/seed/${seed}/${width}/${height}`
}

export function handleCoverError(event: Event, fallbackUrl: string): void {
  const image = event.target as HTMLImageElement
  if (image.dataset.fallbackApplied === '1') {
    image.style.visibility = 'hidden'
    return
  }
  image.dataset.fallbackApplied = '1'
  image.src = fallbackUrl
}
