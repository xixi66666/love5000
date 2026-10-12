import { http } from '@/api/client'

export async function triggerCollectionRefresh(): Promise<void> {
  await http.post('/collections/refresh')
}
