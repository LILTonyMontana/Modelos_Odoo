from odoo import fields, models, api

class SaleLine(models.Model):
    _inherit = 'sale.order.line'
    
    task_id = fields.Many2one(
        'project.task', 'Generated Task', domain="[('sale_line_id.id', '=', id)]")
    
    @api.depends('task_id.quant_progress')
    def _compute_qty_delivered(self):
        for u in self:
            u.qty_delivered = u.task_id.quant_progress
        res = super(SaleLine, self)._compute_qty_delivered()
        return res
