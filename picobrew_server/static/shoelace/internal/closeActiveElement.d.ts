/**
 * Calls the blur method on the current active element if it is a child of the provided element.
 * Needed for fixing a11y errors in console.
 * @see https://github.com/shoelace-style/shoelace/issues/2283
 * @param elm The element to check
 */
export declare const blurActiveElement: (elm: HTMLElement) => void;
