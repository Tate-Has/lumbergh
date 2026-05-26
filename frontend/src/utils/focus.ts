import dayjs from 'dayjs'

export function esc(str: string): string {
  const d = document.createElement('div')
  d.textContent = str
  return d.innerHTML
}

export function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
}

export function todayISO(): string {
  return dayjs().format('YYYY-MM-DD')
}

export function formatDate(date: string): string {
  return dayjs(date).format('ddd, MMM D')
}
