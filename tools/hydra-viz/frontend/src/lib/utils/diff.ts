import type { Ontology, OntologyClass, DataProperty, ObjectProperty } from '$lib/api/types';

/**
 * Represents changes between two ontology states
 */
export interface OntologyDiff {
	classes: {
		added: string[];
		removed: string[];
		modified: string[]; // name changed or subclass changed
	};
	dataProperties: {
		added: string[];
		removed: string[];
		modified: string[];
	};
	objectProperties: {
		added: string[];
		removed: string[];
		modified: string[];
	};
}

/**
 * Check if two arrays have the same elements (order-independent)
 */
const arraysEqual = (a: string[], b: string[]): boolean => {
	if (a.length !== b.length) return false;
	const sortedA = [...a].sort();
	const sortedB = [...b].sort();
	return sortedA.every((v, i) => v === sortedB[i]);
};

/**
 * Check if a class has been modified between two versions
 */
const isClassModified = (prev: OntologyClass, curr: OntologyClass): boolean => {
	// Check if subclass relationships changed
	if (!arraysEqual(prev.sub_class_of, curr.sub_class_of)) return true;

	// Check if description changed significantly
	if (prev.description.definition !== curr.description.definition) return true;
	if (prev.description.constraints !== curr.description.constraints) return true;

	return false;
};

/**
 * Check if a data property has been modified
 */
const isDataPropertyModified = (prev: DataProperty, curr: DataProperty): boolean => {
	if (prev.description !== curr.description) return true;
	if (prev.range !== curr.range) return true;

	// Compare domains (simplified - just check string representations)
	const prevDomains = prev.domain.map((d) => (typeof d === 'string' ? d : JSON.stringify(d)));
	const currDomains = curr.domain.map((d) => (typeof d === 'string' ? d : JSON.stringify(d)));
	if (!arraysEqual(prevDomains, currDomains)) return true;

	return false;
};

/**
 * Check if an object property has been modified
 */
const isObjectPropertyModified = (prev: ObjectProperty, curr: ObjectProperty): boolean => {
	if (prev.description !== curr.description) return true;

	// Compare domains
	const prevDomains = prev.domain.map((d) => (typeof d === 'string' ? d : JSON.stringify(d)));
	const currDomains = curr.domain.map((d) => (typeof d === 'string' ? d : JSON.stringify(d)));
	if (!arraysEqual(prevDomains, currDomains)) return true;

	// Compare ranges
	const prevRanges = prev.range.map((r) => (typeof r === 'string' ? r : JSON.stringify(r)));
	const currRanges = curr.range.map((r) => (typeof r === 'string' ? r : JSON.stringify(r)));
	if (!arraysEqual(prevRanges, currRanges)) return true;

	return false;
};

/**
 * Compute the difference between two ontology states.
 * If previous is null, all items in current are considered "added".
 */
export const computeOntologyDiff = (
	previous: Ontology | null,
	current: Ontology
): OntologyDiff => {
	const diff: OntologyDiff = {
		classes: { added: [], removed: [], modified: [] },
		dataProperties: { added: [], removed: [], modified: [] },
		objectProperties: { added: [], removed: [], modified: [] }
	};

	if (!previous) {
		// Everything in current is "added"
		diff.classes.added = Object.keys(current.classes);
		diff.dataProperties.added = Object.keys(current.data_properties);
		diff.objectProperties.added = Object.keys(current.object_properties);
		return diff;
	}

	const prevClassNames = new Set(Object.keys(previous.classes));
	const currClassNames = new Set(Object.keys(current.classes));

	// Find added, removed, and potentially modified classes
	for (const name of currClassNames) {
		if (!prevClassNames.has(name)) {
			diff.classes.added.push(name);
		} else if (isClassModified(previous.classes[name], current.classes[name])) {
			diff.classes.modified.push(name);
		}
	}
	for (const name of prevClassNames) {
		if (!currClassNames.has(name)) {
			diff.classes.removed.push(name);
		}
	}

	// Data properties
	const prevDataProps = new Set(Object.keys(previous.data_properties));
	const currDataProps = new Set(Object.keys(current.data_properties));

	for (const name of currDataProps) {
		if (!prevDataProps.has(name)) {
			diff.dataProperties.added.push(name);
		} else if (
			isDataPropertyModified(previous.data_properties[name], current.data_properties[name])
		) {
			diff.dataProperties.modified.push(name);
		}
	}
	for (const name of prevDataProps) {
		if (!currDataProps.has(name)) {
			diff.dataProperties.removed.push(name);
		}
	}

	// Object properties
	const prevObjProps = new Set(Object.keys(previous.object_properties));
	const currObjProps = new Set(Object.keys(current.object_properties));

	for (const name of currObjProps) {
		if (!prevObjProps.has(name)) {
			diff.objectProperties.added.push(name);
		} else if (
			isObjectPropertyModified(previous.object_properties[name], current.object_properties[name])
		) {
			diff.objectProperties.modified.push(name);
		}
	}
	for (const name of prevObjProps) {
		if (!currObjProps.has(name)) {
			diff.objectProperties.removed.push(name);
		}
	}

	return diff;
};

/**
 * Check if a diff has any changes
 */
export const hasDiffChanges = (diff: OntologyDiff): boolean => {
	return (
		diff.classes.added.length > 0 ||
		diff.classes.removed.length > 0 ||
		diff.classes.modified.length > 0 ||
		diff.dataProperties.added.length > 0 ||
		diff.dataProperties.removed.length > 0 ||
		diff.dataProperties.modified.length > 0 ||
		diff.objectProperties.added.length > 0 ||
		diff.objectProperties.removed.length > 0 ||
		diff.objectProperties.modified.length > 0
	);
};

/**
 * Get total counts of changes
 */
export const getDiffCounts = (diff: OntologyDiff) => ({
	classes: {
		added: diff.classes.added.length,
		removed: diff.classes.removed.length,
		modified: diff.classes.modified.length,
		total:
			diff.classes.added.length + diff.classes.removed.length + diff.classes.modified.length
	},
	dataProperties: {
		added: diff.dataProperties.added.length,
		removed: diff.dataProperties.removed.length,
		modified: diff.dataProperties.modified.length,
		total:
			diff.dataProperties.added.length +
			diff.dataProperties.removed.length +
			diff.dataProperties.modified.length
	},
	objectProperties: {
		added: diff.objectProperties.added.length,
		removed: diff.objectProperties.removed.length,
		modified: diff.objectProperties.modified.length,
		total:
			diff.objectProperties.added.length +
			diff.objectProperties.removed.length +
			diff.objectProperties.modified.length
	}
});
