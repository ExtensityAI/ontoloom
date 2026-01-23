import Graph from 'graphology';
import type { Sigma } from 'sigma';

export interface NodeAttributes {
	label: string;
	level: number;
	inverseLevel: number;
	parents: Array<string>;
	children: Set<string>;
	edges: Set<string>;
	x?: number;
	y?: number;
}

export interface EdgeAttributes {
	type: string;
	tag: 'hierarchy' | 'property';
	label: string;
	size: number;
	weight: number;
	source: string;
	target: string;
}

export type HydraGraph = Graph<NodeAttributes, EdgeAttributes>;
export type HydraSigma = Sigma<NodeAttributes, EdgeAttributes>;
