<script lang="ts">
  import type { EChartsOption } from "echarts"
  import * as echarts from "echarts"

  let {
    options,
    height = 200
  }: {
    options: EChartsOption | null
    height?: number
  } = $props()

  let container: HTMLDivElement
  let chart: echarts.ECharts | null = $state(null)

  $effect(() => {
    if (!container) return

    const instance = echarts.init(container, undefined, { renderer: "canvas" })
    chart = instance
    const handleResize = () => instance.resize()
    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
      instance.dispose()
      chart = null
    }
  })

  $effect(() => {
    if (!chart) return
    if (!options) {
      chart.clear()
      return
    }
    chart.setOption(options)
  })
</script>

<div bind:this={container} style="height: {height}px;"></div>
