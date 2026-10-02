// 看板与对调页共享的当前周状态，替代原先两处硬编码的 weekId=1
import { ref } from 'vue'
import { api } from './api'

export const weeks = ref([])
export const weekId = ref(null)

export async function loadWeeks(prefer = 'latest') {
  const rows = await api('/weeks')
  weeks.value = rows
  if (!rows.some(w => w.id === weekId.value)) {
    weekId.value = prefer === 'first'
      ? (rows[0]?.id ?? null)
      : Math.max(...rows.map(w => w.id))
  }
  return rows
}

export async function createNextWeek() {
  const w = await api('/weeks', { method: 'POST', body: '{}' })
  await loadWeeks('first')
  weekId.value = w.id
  return w
}
