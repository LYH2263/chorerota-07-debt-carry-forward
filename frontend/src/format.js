// 债余额/数值展示：正=欠债（少做），负=结余/预付（多做，可冲下周）
export function fmtBalance(v) {
  const n = Math.round((Number(v) || 0) * 100) / 100
  if (Math.abs(n) < 0.005) return { text: '0', cls: '' }
  return n > 0
    ? { text: '欠 ' + n.toFixed(2), cls: 'debt' }
    : { text: '余 ' + (-n).toFixed(2), cls: 'credit' }
}

export const fmtNum = (v) =>
  (v === null || v === undefined) ? '—'
  : (Math.abs(Number(v)) < 0.005 ? '0' : Number(v).toFixed(2))
