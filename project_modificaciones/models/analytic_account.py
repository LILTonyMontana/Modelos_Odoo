from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
_logger = logging.getLogger(__name__)

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'
    
    is_provisional = fields.Boolean(string="Es Provisional", default=False)
    
    readonly_plan = fields.Boolean(compute='_compute_readonly_plan', store=False)

    def _compute_readonly_plan(self):
        for rec in self:
            rec.readonly_plan = self.env.context.get('set_provisional_defaults', False)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if self.env.context.get('set_provisional_defaults'):
            _logger.info("✅ Contexto detectado: set_provisional_defaults = True")
            vals['is_provisional'] = True
            vals['plan_id'] = self._get_default_analytic_plan_id()
        return vals

    @api.model
    def _get_default_analytic_plan_id(self):
        plans = self.env['account.analytic.plan'].search([])
        for plan in plans:
            if plan.name == 'Centro de costo':
                return plan.id
        raise UserError(_("El plan analítico 'Centro de costo' no existe. Por favor, créalo primero."))



    def write(self, vals):
        for record in self:
            if 'plan_id' in vals and record.is_provisional:
                raise ValidationError(_("No se puede modificar el plan en cuentas provisionales"))
        return super().write(vals)