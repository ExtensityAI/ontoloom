# hydra-viz frontend

Interactive web UI for exploring ontology-hydra runs. Built with SvelteKit 2, Svelte 5, and TypeScript.

## Tech Stack

- **Framework**: [SvelteKit](https://svelte.dev/docs/kit) with static adapter
- **Graph Rendering**: [Sigma.js](https://www.sigmajs.org/) + [Graphology](https://graphology.github.io/) with ForceAtlas2 layout
- **Charts**: [ECharts](https://echarts.apache.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/) v4
- **Icons**: [Lucide](https://lucide.dev/)

## Development

Requires [pnpm](https://pnpm.io/) and Node.js.

```bash
pnpm install
pnpm dev
```

The dev server proxies API requests to the backend. Make sure `hydra-viz` is running on port 8080.

## Pages

| Route | Description |
|-------|-------------|
| `/` | Run listing with titles and timestamps |
| `/runs/[name]` | Run summary with metrics charts |
| `/runs/[name]/[iter]` | Iteration dashboard with metric cards and deltas |
| `/runs/[name]/[iter]/graph` | Interactive ontology graph visualization |
| `/runs/[name]/[iter]/changes` | Plan, operations, and review for the iteration |

## Building

```bash
pnpm build
```

Output goes to `build/`. The parent Makefile copies this into the Python package's static directory for bundled distribution.

## Linting & Formatting

```bash
pnpm lint       # check with Prettier + ESLint
pnpm format     # auto-format with Prettier
pnpm check      # Svelte type checking
```
