<script module lang="ts">
  import rehypeSanitize from "rehype-sanitize"
  import rehypeStringify from "rehype-stringify"
  import remarkGfm from "remark-gfm"
  import remarkParse from "remark-parse"
  import remarkRehype from "remark-rehype"
  import { unified } from "unified"

  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkRehype)
    .use(rehypeSanitize)
    .use(rehypeStringify)
</script>

<script lang="ts">
  const { content }: { content: string } = $props()

  let html = $state("")

  $effect(() => {
    processor.process(content).then((result) => {
      html = result.toString()
    })
  })
</script>

<div class="prose">
  {#if html}
    {@html html}
  {/if}
</div>

<style>
  .prose :global(h1) {
    font-size: 1.25rem;
    font-weight: 600;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
  }

  .prose :global(h2) {
    font-size: 1.125rem;
    font-weight: 600;
    margin-top: 1.25rem;
    margin-bottom: 0.5rem;
  }

  .prose :global(h3) {
    font-size: 1rem;
    font-weight: 600;
    margin-top: 1rem;
    margin-bottom: 0.5rem;
  }

  .prose :global(p) {
    margin-bottom: 0.75rem;
  }

  .prose :global(ul),
  .prose :global(ol) {
    margin-bottom: 0.75rem;
    padding-left: 1.5rem;
  }

  .prose :global(ul) {
    list-style-type: disc;
  }

  .prose :global(ol) {
    list-style-type: decimal;
  }

  .prose :global(li) {
    margin-bottom: 0.25rem;
  }

  .prose :global(code) {
    font-family: var(--font-mono, monospace);
    font-size: 0.875em;
    background: var(--color-surface, #1a1a1a);
    padding: 0.125rem 0.25rem;
    border-radius: 0.25rem;
  }

  .prose :global(pre) {
    font-family: var(--font-mono, monospace);
    font-size: 0.875rem;
    background: var(--color-surface, #1a1a1a);
    padding: 0.75rem 1rem;
    border-radius: 0.25rem;
    overflow-x: auto;
    margin-bottom: 0.75rem;
  }

  .prose :global(pre code) {
    background: none;
    padding: 0;
  }

  .prose :global(blockquote) {
    border-left: 2px solid var(--color-edge, #333);
    padding-left: 1rem;
    margin-bottom: 0.75rem;
    color: var(--color-muted, #888);
  }

  .prose :global(strong) {
    font-weight: 600;
  }

  .prose :global(a) {
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .prose :global(hr) {
    border: none;
    border-top: 1px solid var(--color-edge, #333);
    margin: 1rem 0;
  }

  .prose :global(table) {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 0.75rem;
  }

  .prose :global(th),
  .prose :global(td) {
    border: 1px solid var(--color-edge, #333);
    padding: 0.5rem 0.75rem;
    text-align: left;
  }

  .prose :global(th) {
    font-weight: 600;
    background: var(--color-surface, #1a1a1a);
  }

  .prose :global(tr:nth-child(even)) {
    background: var(--color-surface, #1a1a1a);
  }
</style>
