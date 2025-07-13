/** @odoo-module **/
import { FormLabel } from "@web/views/form/form_label";
import { patch } from "@web/core/utils/patch";

patch(FormLabel.prototype, {
    /**
     * @override
     */
    setup() {
        super.setup();
        if (this.props.fieldInfo.required) {
            this.props.field_required = true
        }
    }
});

