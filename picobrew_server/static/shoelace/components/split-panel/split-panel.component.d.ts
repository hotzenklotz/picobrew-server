import ShoelaceElement from '../../internal/shoelace-element.js';
import type { CSSResultGroup } from 'lit';
export interface SnapFunctionParams {
    /** The position the divider has been dragged to, in pixels. */
    pos: number;
    /** The size of the split-panel across its primary axis, in pixels. */
    size: number;
    /** The snap-threshold passed to the split-panel, in pixels. May be infinity. */
    snapThreshold: number;
    /** Whether or not the user-agent is RTL. */
    isRtl: boolean;
    /** Whether or not the split panel is vertical. */
    vertical: boolean;
}
/** Used by sl-split-panel to convert an input position into a snapped position. */
export type SnapFunction = (opt: SnapFunctionParams) => number | null;
/** A SnapFunction which performs no snapping. */
export declare const SNAP_NONE: () => null;
/**
 * @summary Split panels display two adjacent panels, allowing the user to reposition them.
 * @documentation https://shoelace.style/components/split-panel
 * @status stable
 * @since 2.0
 *
 * @event sl-reposition - Emitted when the divider's position changes.
 *
 * @slot start - Content to place in the start panel.
 * @slot end - Content to place in the end panel.
 * @slot divider - The divider. Useful for slotting in a custom icon that renders as a handle.
 *
 * @csspart start - The start panel.
 * @csspart end - The end panel.
 * @csspart panel - Targets both the start and end panels.
 * @csspart divider - The divider that separates the start and end panels.
 *
 * @cssproperty [--divider-width=4px] - The width of the visible divider.
 * @cssproperty [--divider-hit-area=12px] - The invisible region around the divider where dragging can occur. This is
 *  usually wider than the divider to facilitate easier dragging.
 * @cssproperty [--min=0] - The minimum allowed size of the primary panel.
 * @cssproperty [--max=100%] - The maximum allowed size of the primary panel.
 */
export default class SlSplitPanel extends ShoelaceElement {
    static styles: CSSResultGroup;
    private cachedPositionInPixels;
    private isCollapsed;
    private readonly localize;
    private positionBeforeCollapsing;
    private resizeObserver;
    private size;
    divider: HTMLElement;
    /**
     * The current position of the divider from the primary panel's edge as a percentage 0-100. Defaults to 50% of the
     * container's initial size.
     */
    position: number;
    /** The current position of the divider from the primary panel's edge in pixels. */
    positionInPixels: number;
    /** Draws the split panel in a vertical orientation with the start and end panels stacked. */
    vertical: boolean;
    /** Disables resizing. Note that the position may still change as a result of resizing the host element. */
    disabled: boolean;
    /**
     * If no primary panel is designated, both panels will resize proportionally when the host element is resized. If a
     * primary panel is designated, it will maintain its size and the other panel will grow or shrink as needed when the
     * host element is resized.
     */
    primary?: 'start' | 'end';
    private snapValue;
    private snapFunction;
    /**
     * Converts a string containing either a series of fixed/repeated snap points (e.g. "repeat(20%)", "100px 200px 800px", or "10% 50% repeat(10px)") into a SnapFunction. `SnapFunction`s take in a `SnapFunctionOpts` and return the position that the split panel should snap to.
     *
     * @param snap - The snap string.
     * @returns a `SnapFunction` representing the snap string's logic.
     */
    private toSnapFunction;
    /**
     * Either one or more space-separated values at which the divider should snap, in pixels, percentages, or repeat expressions e.g. `'100px 50% 500px' or `repeat(50%) 10px`,
     * or a function which takes in a `SnapFunctionParams`, and returns a position to snap to, e.g. `({ pos }) => Math.round(pos / 8) * 8`.
     */
    set snap(snap: string | SnapFunction | null | undefined);
    get snap(): string | SnapFunction;
    /** How close the divider must be to a snap point until snapping occurs. */
    snapThreshold: number;
    connectedCallback(): void;
    disconnectedCallback(): void;
    private detectSize;
    private percentageToPixels;
    private pixelsToPercentage;
    private handleDrag;
    private handleKeyDown;
    private handleResize;
    handlePositionChange(): void;
    handlePositionInPixelsChange(): void;
    handleVerticalChange(): void;
    render(): import("lit-html").TemplateResult<1>;
}
declare global {
    interface HTMLElementTagNameMap {
        'sl-split-panel': SlSplitPanel;
    }
}
