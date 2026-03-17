import adapter from '@sveltejs/adapter-static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	kit: {
		adapter: adapter({
			pages: 'build',
			assets: 'build',
			fallback: 'index.html', // SPA mode - serve index.html for all routes
			precompress: false,
			strict: true
		}),
		paths: {
			base: '' // Serve from root
		}
	}
};

export default config;
