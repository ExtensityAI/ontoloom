import Graph from 'graphology';
import type { Ontology, OntologyClass, ClassExpression } from '$lib/api/types';
import type { EdgeAttributes, NodeAttributes } from './types';
import { type HydraGraph } from './types';

// Layout constants
const LEVEL_HEIGHT = 120;
const NODE_SPACING = 100;
const MIN_HORIZONTAL_GAP = 80;

/**
 * Compute hierarchy depth for each class by traversing superclass chains.
 * For multiple inheritance, uses max depth from any parent path.
 */
const computeClassLevels = (classes: Record<string, OntologyClass>): Map<string, number> => {
	const levels = new Map<string, number>();

	const getLevel = (name: string, visited = new Set<string>()): number => {
		if (levels.has(name)) return levels.get(name)!;
		if (visited.has(name)) return 0; // cycle protection

		visited.add(name);
		const cls = classes[name];
		if (!cls || cls.sub_class_of.length === 0) {
			levels.set(name, 0);
			return 0;
		}

		// Use max depth from all parents for consistent layering
		const maxParentLevel = Math.max(
			...cls.sub_class_of.map((parent) => getLevel(parent, new Set(visited)))
		);
		const level = maxParentLevel + 1;
		levels.set(name, level);
		return level;
	};

	Object.keys(classes).forEach((name) => getLevel(name));
	return levels;
};

/**
 * Compute hierarchical layout positions for nodes.
 * Y-axis: based on level (root at top, leaves at bottom)
 * X-axis: distribute siblings evenly, try to center under parent
 */
const computeHierarchicalLayout = (
	graph: HydraGraph,
	classes: Record<string, OntologyClass>,
	classLevels: Map<string, number>,
	maxLevel: number
): void => {
	// Group nodes by level
	const levelNodes: Map<number, string[]> = new Map();
	graph.forEachNode((node, attrs) => {
		const level = attrs.level;
		if (!levelNodes.has(level)) levelNodes.set(level, []);
		levelNodes.get(level)!.push(node);
	});

	// Sort nodes within each level to group siblings together
	// Nodes with the same parent should be adjacent
	levelNodes.forEach((nodes, level) => {
		if (level === 0) {
			// Root level: sort alphabetically for consistency
			nodes.sort();
		} else {
			// Other levels: sort by first parent, then alphabetically
			nodes.sort((a, b) => {
				const parentA = classes[a]?.sub_class_of[0] ?? '';
				const parentB = classes[b]?.sub_class_of[0] ?? '';
				if (parentA !== parentB) return parentA.localeCompare(parentB);
				return a.localeCompare(b);
			});
		}
	});

	// Position nodes level by level
	levelNodes.forEach((nodes, level) => {
		const y = level * LEVEL_HEIGHT;
		const totalWidth = Math.max((nodes.length - 1) * NODE_SPACING, nodes.length * MIN_HORIZONTAL_GAP);
		const startX = -totalWidth / 2;

		nodes.forEach((node, i) => {
			const spacing = nodes.length > 1 ? totalWidth / (nodes.length - 1) : 0;
			const x = nodes.length === 1 ? 0 : startX + i * spacing;
			graph.setNodeAttribute(node, 'x', x);
			graph.setNodeAttribute(node, 'y', y);
		});
	});

	// Second pass: try to center children under their parents
	// Iterate from bottom to top
	for (let level = maxLevel; level > 0; level--) {
		const nodes = levelNodes.get(level) ?? [];

		// Group nodes by their primary parent
		const parentGroups: Map<string, string[]> = new Map();
		nodes.forEach((node) => {
			const parent = classes[node]?.sub_class_of[0];
			if (parent && graph.hasNode(parent)) {
				if (!parentGroups.has(parent)) parentGroups.set(parent, []);
				parentGroups.get(parent)!.push(node);
			}
		});

		// Adjust parent X to be centered over children
		parentGroups.forEach((children, parent) => {
			if (children.length === 0) return;
			const childXs = children.map((c) => graph.getNodeAttribute(c, 'x') ?? 0);
			const centerX = childXs.reduce((sum, x) => sum + x, 0) / children.length;
			graph.setNodeAttribute(parent, 'x', centerX);
		});
	}

	// Third pass: spread out roots to avoid overlap
	const roots = levelNodes.get(0) ?? [];
	if (roots.length > 1) {
		const rootWidth = (roots.length - 1) * NODE_SPACING * 1.5;
		const rootStartX = -rootWidth / 2;
		roots.forEach((node, i) => {
			graph.setNodeAttribute(node, 'x', rootStartX + i * NODE_SPACING * 1.5);
		});
	}
};

/**
 * Extract class names from a domain/range expression.
 * Can be either a string (single class) or ClassExpression (intersection).
 */
const extractClassNames = (expr: string | ClassExpression): string[] => {
	if (typeof expr === 'string') return [expr];
	return expr.intersectionOf ?? [];
};

export const createOntologyGraph = (ontology: Ontology) => {
	const G: HydraGraph = new Graph<NodeAttributes, EdgeAttributes>({
		multi: true,
		type: 'mixed'
	});

	const classLevels = computeClassLevels(ontology.classes);
	const maxLevel = Math.max(...classLevels.values(), 0);

	// Add class nodes with placeholder positions (will be set by layout)
	Object.entries(ontology.classes).forEach(([name, cls]) => {
		const level = classLevels.get(name) ?? 0;

		G.addNode(name, {
			label: name,
			level,
			inverseLevel: maxLevel - level,
			parents: [],
			children: new Set<string>(),
			x: 0,
			y: 0
		});
	});

	// Add hierarchy edges (subclass -> superclasses)
	Object.entries(ontology.classes)
		.filter(([, cls]) => cls.sub_class_of.length > 0)
		.forEach(([name, cls]) => {
			cls.sub_class_of.forEach((parent) => {
				// Skip if parent node doesn't exist
				if (!G.hasNode(parent)) return;

				const edgeKey = `${name}-is-a->${parent}`;

				G.addDirectedEdgeWithKey(edgeKey, name, parent, {
					type: 'arrow',
					tag: 'hierarchy',
					label: 'isA',
					size: 2,
					weight: 5,
					source: name,
					target: parent
				});

				// Update children set
				G.getNodeAttributes(parent).children.add(name);
			});
		});

	// Add object property edges (domain -> range)
	Object.entries(ontology.object_properties).forEach(([propName, prop]) => {
		const domains = prop.domain.flatMap(extractClassNames);
		const ranges = prop.range.flatMap(extractClassNames);

		domains.forEach((domain) => {
			if (!G.hasNode(domain)) return;

			ranges.forEach((range) => {
				if (!G.hasNode(range)) return;

				const edgeKey = `${domain}-${propName}->${range}`;

				G.addDirectedEdgeWithKey(edgeKey, domain, range, {
					type: 'line',
					tag: 'property',
					label: propName,
					size: 1,
					weight: 1,
					source: domain,
					target: range
				});
			});
		});
	});

	// add parent chains to node attributes (all ancestors via BFS)
	Object.entries(ontology.classes).forEach(([name, cls]) => {
		const attrs = G.getNodeAttributes(name);
		const visited = new Set<string>();
		const queue = [...cls.sub_class_of];

		while (queue.length > 0) {
			const parent = queue.shift()!;
			if (visited.has(parent)) continue;
			visited.add(parent);
			attrs.parents.push(parent);

			const parentCls = ontology.classes[parent];
			if (parentCls) {
				queue.push(...parentCls.sub_class_of);
			}
		}
	});

	// Compute hierarchical layout positions
	computeHierarchicalLayout(G, ontology.classes, classLevels, maxLevel);

	return G;
};
