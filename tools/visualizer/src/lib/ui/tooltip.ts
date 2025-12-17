import type { Action } from "svelte/action"

const DELAY = 250 // ms

export const tooltip: Action<HTMLElement, string> = (node, text) => {
	let tip: HTMLElement | null = null
	let timeout: ReturnType<typeof setTimeout> | null = null

	function show() {
		if (tip) return
		tip = document.createElement("div")
		tip.className = "tooltip"
		tip.textContent = text
		document.body.appendChild(tip)
		position()
	}

	function hide() {
		if (timeout) {
			clearTimeout(timeout)
			timeout = null
		}
		tip?.remove()
		tip = null
	}

	function scheduleShow() {
		if (timeout) return
		timeout = setTimeout(() => {
			timeout = null
			show()
		}, DELAY)
	}

	function position() {
		if (!tip) return
		const rect = node.getBoundingClientRect()
		const tipRect = tip.getBoundingClientRect()
		
		// Center above element, but clamp to viewport
		const idealLeft = rect.left + rect.width / 2 - tipRect.width / 2
		const left = Math.max(8, Math.min(idealLeft, window.innerWidth - tipRect.width - 8))
		
		// Arrow points to element center relative to tooltip
		const arrowLeft = rect.left + rect.width / 2 - left
		tip.style.setProperty("--arrow-left", `${arrowLeft}px`)
		
		tip.style.left = `${left}px`
		tip.style.top = `${rect.top - tipRect.height - 2}px`
	}

	node.addEventListener("mouseenter", scheduleShow)
	node.addEventListener("mouseleave", hide)
	node.addEventListener("focus", scheduleShow)
	node.addEventListener("blur", hide)

	return {
		update(newText: string) {
			text = newText
			if (tip) tip.textContent = text
		},
		destroy() {
			hide()
			node.removeEventListener("mouseenter", scheduleShow)
			node.removeEventListener("mouseleave", hide)
			node.removeEventListener("focus", scheduleShow)
			node.removeEventListener("blur", hide)
		},
	}
}