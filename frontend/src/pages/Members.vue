<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <ul class="list">
      <li v-for="m in rows" :key="m.id" class="member-row" @click="toggle(m.id)">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <span class="chip" :class="debtClass(m.current_debt)">
          当前债 {{ fmt(m.current_debt) }}<template v-if="m.label"> · {{ m.label }}</template>
        </span>
        <span class="muted">点击{{ open === m.id ? '收起' : '按周回看' }}</span>

        <table v-if="open === m.id" class="debt-table" @click.stop>
          <thead>
            <tr><th>周</th><th>占格</th><th>权重</th><th>债前</th><th>本周</th><th>债后</th></tr>
          </thead>
          <tbody>
            <tr v-if="!hist[m.id] || !hist[m.id].weeks.length">
              <td colspan="6" class="muted">该成员尚无已落定周</td>
            </tr>
            <tr v-for="w in (hist[m.id] ? hist[m.id].weeks : [])" :key="w.week_id">
              <td>{{ w.label || ('第' + w.week_id + '周') }}</td>
              <td>{{ w.slots }} 格</td>
              <td>{{ fmt(w.load) }}</td>
              <td :class="debtClass(w.before)">{{ fmt(w.before) }}</td>
              <td :class="debtClass(w.delta)">
                {{ (w.delta > 0 ? '+' : '') + fmt(w.delta) }}
                <span v-if="w.frozen" class="chip frozen">冻结</span>
              </td>
              <td :class="debtClass(w.after)"><strong>{{ fmt(w.after) }}</strong></td>
            </tr>
          </tbody>
        </table>
      </li>
    </ul>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
const rows = ref([])
const hist = ref({})
const open = ref(null)
const name = ref('')
function fmt(x) { return (x ?? 0).toFixed(1).replace(/\.0$/, '') }
function debtClass(x) { return x > 1e-6 ? 'coral' : (x < -1e-6 ? 'debt-neg-chip' : '') }
async function load() { rows.value = await api('/members/debt') }
async function toggle(id) {
  if (open.value === id) { open.value = null; return }
  open.value = id
  if (!hist.value[id]) hist.value[id] = await api('/members/' + id + '/debt')
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
