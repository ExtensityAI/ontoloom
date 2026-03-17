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

  <label
    class="inline-flex cursor-text items-center gap-1.5 rounded border border-edge bg-surface/50 px-2
         py-0.5 font-mono text-sm leading-5 text-fg
         focus-within:outline-2 focus-within:outline-green-500"
  >
    <input
      type="number"
      min="0"
      {max}
      value={current}
      inputmode="numeric"
      class="w-[2ch] shrink-0 [appearance:textfield] bg-transparent p-0 text-end
           tabular-nums outline-none
           [&::-webkit-inner-spin-button]:appearance-none
           [&::-webkit-outer-spin-button]:appearance-none"
      onkeydown={onKeyDown}
      onblur={onBlur}
    />
    <span class="leading-5 text-faint select-none">/</span>
    <span class="w-[2ch] shrink-0 text-start leading-5 text-faint tabular-nums select-none">
      {max}
    </span>
  </label>

  {#if hasNext}
    <a href={getHref(current + 1)} class="px-1.5 py-1 text-faint transition-colors hover:text-fg"
      ><ChevronRight size={16} /></a
    >
  {:else}
    <span class="px-1.5 py-1 text-faint/30"><ChevronRight size={16} /></span>
  {/if}
</div>
