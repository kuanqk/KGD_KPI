<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import {
  Chart,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Tooltip,
  Legend,
} from 'chart.js'

Chart.register(
  LineController, LineElement, PointElement,
  LinearScale, CategoryScale, Tooltip, Legend,
)

const props = defineProps({
  labels: {
    type: Array,
    required: true,
  },
  datasets: {
    type: Array,
    required: true,
  },
  title: {
    type: String,
    default: '',
  },
  yMax: {
    type: Number,
    default: null,
  },
})

const canvasRef = ref(null)
let chartInstance = null

function buildChart() {
  if (!canvasRef.value) return
  if (chartInstance) chartInstance.destroy()

  chartInstance = new Chart(canvasRef.value, {
    type: 'line',
    data: {
      labels: props.labels,
      datasets: props.datasets.map(ds => ({
        tension: 0.3,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2,
        fill: false,
        ...ds,
      })),
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: 12 }, boxWidth: 14, padding: 12 },
        },
        tooltip: { mode: 'index', intersect: false },
        title: props.title
          ? { display: true, text: props.title, font: { size: 14 } }
          : { display: false },
      },
      scales: {
        x: {
          grid: { color: '#F0F0F0' },
          ticks: { font: { size: 11 } },
        },
        y: {
          min: 0,
          max: props.yMax ?? undefined,
          grid: { color: '#F0F0F0' },
          ticks: { font: { size: 11 } },
        },
      },
      interaction: { mode: 'nearest', axis: 'x', intersect: false },
    },
  })
}

onMounted(() => buildChart())
onUnmounted(() => { if (chartInstance) chartInstance.destroy() })
watch(() => [props.labels, props.datasets], () => buildChart(), { deep: true })
</script>

<template>
  <div class="chart-wrap">
    <canvas ref="canvasRef"></canvas>
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 260px;
}
</style>
