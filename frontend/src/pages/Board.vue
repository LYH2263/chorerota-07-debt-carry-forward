<template>
  <div>
    <h1 class="brand">本周看板</h1>
    <p class="muted">周卡片网格 · 生成时按欠班债优先派格偿还，可去「对调」申请交换</p>

    <div class="week-bar">
      <select v-model.number="weekId" @change="load">
        <option v-for="w in weeks" :key="w.id" :value="w.id">{{ w.label }} · {{ w.status }}</option>
      </select>
      <button class="ghost" @click="newWeek">新建周</button>
      <button @click="generate">生成周表</button>
      <button class="ghost" @click="load">刷新</button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>

    <section v-if="debt && debt.members.length" class="week-card debt-panel">
      <header>
        欠班债结算
        <span v-if="debt.frozen" class="chip frozen">已冻结 · 活跃不足，旧债原样结转</span>
      </header>
      <table class="debt-table">
        <thead>
          <tr><th>成员</th><th>本周占格</th><th>占格权重</th><th>债前</th><th>本周</th><th>债后</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in debt.members" :key="d.member_id">
            <td>{{ d.name }}</td>
            <td>{{ d.slots }} 格</td>
            <td>{{ fmt(d.load) }}</td>
            <td :class="debtClass(d.before)">{{ fmt(d.before) }}</td>
            <td :class="debtClass(d.delta)">{{ signed(d.delta) }}</td>
            <td :class="debtClass(d.after)"><strong>{{ fmt(d.after) }}</strong></td>
          </tr>
        </tbody>
      </table>
      <p class="muted" v-if="!debt.frozen">正数=欠班（下周优先多派偿还）· 负数=多做贷项（冲抵下周）</p>
    </section>

    <div class="week-grid">
      <article v-for="d in days" :key="d" class="week-card">
        <header>Day {{ d }}</header>
        <div v-for="a in byDay(d)" :key="a.id">
          <span class="chip">{{ a.task_title }}</span>
          <span class="chip coral">{{ a.member_name }}</span>
        </div>
        <p v-if="!byDay(d).length" class="muted">空</p>
      </article>
    </div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const assigns = ref([])
const weeks = ref([])
const weekId = ref(1)
const debt = ref(null)
const days = [0,1,2,3,4,5,6]
const err = ref('')
function byDay(d) { return assigns.value.filter(a => a.day === d) }
function fmt(x) { return (x ?? 0).toFixed(1).replace(/\.0$/, '') }
function signed(x) { return (x > 0 ? '+' : '') + fmt(x) }
function debtClass(x) { return x > 1e-6 ? 'debt-pos' : (x < -1e-6 ? 'debt-neg' : '') }
async function loadWeeks() {
  weeks.value = await api('/weeks')
  if (!weeks.value.find(w => w.id === weekId.value) && weeks.value.length)
    weekId.value = weeks.value[weeks.value.length - 1].id
}
async function load() {
  err.value = ''
  try {
    const b = await api('/weeks/' + weekId.value + '/board')
    assigns.value = b.assignments || []
    debt.value = b.debt || null
  } catch (e) { err.value = e.message }
}
async function generate() {
  err.value = ''
  try {
    const r = await api('/weeks/' + weekId.value + '/generate', { method: 'POST', body: '{}' })
    debt.value = r.debt || null
    await loadWeeks(); await load()
  } catch (e) { err.value = e.message }
}
async function newWeek() {
  err.value = ''
  try {
    const w = await api('/weeks', { method: 'POST', body: JSON.stringify({ label: '第' + (weeks.value.length + 1) + '周' }) })
    await loadWeeks(); weekId.value = w.id; await load()
  } catch (e) { err.value = e.message }
}
onMounted(async () => { await loadWeeks(); await load() })
</script>
