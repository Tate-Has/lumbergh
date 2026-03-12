export function getApiBase(): string {
  return `${window.location.protocol}//${window.location.host}/api`
}

export function getWsBase(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/api`
}
