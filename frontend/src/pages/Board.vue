<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">周卡片网格 · 生成即落钉（占格快照与债务台账不可回刷），落定后可去「对调」申请交换</p>
    <div class="week-bar">
      <select v-model.number="weekId" @change="load">
        <option v-for="w in weeks" :key="w.id" :value="w.id">
          #{{ w.id }} · {{ w.label }} · {{ w.status }}{{ w.frozen ? ' · 冻结' : '' }}
        </option>
      </select>
      <button class="ghost" @click="nextWeek">新建下一周</button>
    </div>
    <div style="display:flex;gap:8px;margin:12px 0">
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>Day {{ d }}</header>
        <div v-for="a in byDay(d)" :key="a.id">
          <span class="chip">{{ a.task_title }}<template v-if="a.task_weight !== null"> · 重{{ a.task_weight }}</template></span>
          <span class="chip coral">{{ a.member_name }}</span>
        </div>
        <p v-if="!byDay(d).length" class="muted">空</p>
      </article>
    </div>

    <h2 class="brand" style="font-size:17px;margin-top:18px">占格与欠班债</h2>
    <span v-if="ledger.frozen" class="chip amber">冻结周 · 债不结算，余额结转</span>
    <table v-if="ledger.pinned" class="table">
      <thead>
        <tr>
          <th>成员</th><th class="num">格位数</th><th class="num">权重负载</th>
          <th class="num">周均值</th><th class="num">债前</th><th class="num">债后</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in ledger.rows" :key="r.member_id">
          <td>{{ r.member_name }}</td>
          <td class="num">{{ r.slots }}</td>
          <td class="num">{{ r.load }}</td>
          <td class="num">{{ fmtNum(r.avg_load) }}</td>
          <td class="num" :class="fmtBalance(r.debt_before).cls">{{ fmtBalance(r.debt_before).text }}</td>
          <td class="num" :class="fmtBalance(r.debt_after).cls">{{ fmtBalance(r.debt_after).text }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="week && week.status === 'ready'" class="muted ledger-note">该周为旧版周表，未钉债务账。</p>
    <p v-if="ledger.pinned" class="muted ledger-note">占用为落定快照；对调不改已钉债，下周记债只认钉账。</p>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { weeks, weekId, loadWeeks, createNextWeek } from '../weeks'
import { fmtBalance, fmtNum } from '../format'
const assigns = ref([])
const ledger = ref({ pinned: false, frozen: 0, mean: null, rows: [] })
const week = ref(null)
const days = [0,1,2,3,4,5,6]
const err = ref('')
function byDay(d) { return assigns.value.filter(a => a.day === d) }
async function load() {
  err.value = ''
  if (!weekId.value) return
  try {
    const b = await api('/weeks/' + weekId.value + '/board')
    assigns.value = b.assignments || []
    ledger.value = b.ledger || { pinned: false, rows: [] }
    week.value = b.week
  } catch (e) { err.value = e.message }
}
async function generate() {
  err.value = ''
  try {
    await api('/weeks/' + weekId.value + '/generate', { method: 'POST', body: '{}' })
    await load()
  } catch (e) {
    err.value = e.message === 'week_already_settled' ? '该周已落钉，不可重新生成（可新建下一周）' : e.message
  }
}
async function nextWeek() {
  err.value = ''
  try { await createNextWeek(); await load() }
  catch (e) { err.value = e.message }
}
onMounted(async () => { await loadWeeks(); await load() })
</script>
