from odoo import fields, models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    sproject_id = fields.Many2one('project.project', 'Proyecto', domain="[('sale_order_id.id', '=', id)]")
    project_sub_updates = fields.One2many('project.sub.update', 'sale_order_id', string='Avances del Proyecto')

    serv_assig = fields.Selection(
            [('assig', 'Con OS'),
             ('no_assig', 'Sin OS')],
            string='Estatus de servicio', 
            required=True, tracking=True, default='assig')