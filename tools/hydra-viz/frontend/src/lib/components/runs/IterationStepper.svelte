<script lang="ts">
  import { goto } from "$app/navigation"
  import { ChevronLeft, ChevronRight } from "@lucide/svelte"

  const {
    current,
    max,
    getHref
  }: {
    current: number
    max: number
    getHref: (iter: number) => string
  } = $props()

  const hasPrev = $derived(current > 0)
  const hasNext = $derived(current < max)

  const navigate = (value: number) => {
    const clamped = Math.max(0, Math.min(max, value))
    if (clamped !== current) goto(getHref(clamped))
  }

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault()
      const value = parseInt((e.currentTarget as HTMLInputElement).value)
      navigate(value)
    }
  }

  const onBlur = (e: FocusEvent) => {
    const value = parseInt((e.currentTarget as HTMLInputElement).value)
    navigate(value)
  }
</script>

<div class="flex items-center">
  <span class="px-2 py-1 text-faint">iter</span>

  {#if hasPrev}
    <a href={getHref(current - 1)} class="px-1.5 py-1 text-faint transition-colors hover:text-fg"
      ><ChevronLeft size={16} /></a
    >
  {:else}
    <span class="px-1.5 py-1 text-faint/30"><ChevronLeft size={16} /></span>
  {/if}

  <div class="flex items-center border border-edge bg-surface/50 px-2 py-0.5">
    <input
      type="number"
      min="0"
      {max}
      value={current}
      class="w-6 [appearance:textfield] bg-transparent text-center text-fg [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      onkeydown={onKeyDown}
      onblur={onBlur}
    />
    <span class="text-faint">/ {max}</span>
  </div>

  {#if hasNext}
    <a href={getHref(current + 1)} class="px-1.5 py-1 text-faint transition-colors hover:text-fg"
      ><ChevronRight size={16} /></a
    >
  {:else}
    <span class="px-1.5 py-1 text-faint/30"><ChevronRight size={16} /></span>
  {/if}
</div>
