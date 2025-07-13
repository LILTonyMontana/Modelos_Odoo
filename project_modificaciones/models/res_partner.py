import random
from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    def _get_color(self):
        return random.randint(1, 11)
    
    project_tag_id = fields.Many2many('project.tags', 'Especialidad')
    color = fields.Integer(string='Color', default=_get_color)
