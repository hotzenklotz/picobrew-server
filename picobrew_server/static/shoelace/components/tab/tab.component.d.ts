import ShoelaceElement from '../../internal/shoelace-element.js';
import SlIconButton from '../icon-button/icon-button.component.js';
import type { CSSResultGroup } from 'lit';
/**
 * @summary Tabs are used inside [tab groups](/components/tab-group) to represent and activate [tab panels](/components/tab-panel).
 * @documentation https://shoelace.style/components/tab
 * @status stable
 * @since 2.0
 *
 * @dependency sl-icon-button
 *
 * @slot - The tab's label.
 *
 * @event sl-close - Emitted when the tab is closable and the close button is activated.
 *
 * @csspart base - The component's base wrapper.
 * @csspart close-button - The close button, an `<sl-icon-button>`.
 * @csspart close-button__base - The close button's exported `base` part.
 */
export default class SlTab extends ShoelaceElement {
    static styles: CSSResultGroup;
    static dependencies: {
        'sl-icon-button': typeof SlIconButton;
    };
    private readonly localize;
    private readonly attrId;
    private readonly componentId;
    tab: HTMLElement;
    /** The name of the tab panel this tab is associated with. The panel must be located in the same tab group. */
    panel: string;
    /** Draws the tab in an active state. */
    active: boolean;
    /** Makes the tab closable and shows a close button. */
    closable: boolean;
    /** Disables the tab and prevents selection. */
    disabled: boolean;
    /**
     * @internal
     * Need to wrap in a `@property()` otherwise CustomElement throws a "The result must not have attributes" runtime error.
     */
    tabIndex: number;
    connectedCallback(): void;
    private handleCloseClick;
    handleActiveChange(): void;
    handleDisabledChange(): void;
    render(): import("lit-html").TemplateResult<1>;
}
declare global {
    interface HTMLElementTagNameMap {
        'sl-tab': SlTab;
    }
}
