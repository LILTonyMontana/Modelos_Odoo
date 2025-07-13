from odoo import models, fields, api, _
from datetime import datetime
from odoo.exceptions import ValidationError

class PendingService(models.Model):
    _name = 'pending.service'
    _description = 'Servicio Pendiente'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Nombre",
        required=True, copy=False, readonly=True,
        index='trigram',
        default=lambda self: _('New'))
    order_number = fields.Char(string='Número de Orden', tracking=True)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('assigned', 'Asignada'),
        ('canceled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)
    supervisor_id = fields.Many2one('hr.employee', string='Supervisor', tracking=True)
    disciplina_id = fields.Many2one('license.disciplina', string='Disciplina', required=True, tracking=True)
    service_line_ids = fields.One2many('pending.service.line', 'service_id', string='Líneas de Servicio', delete='cascade')
    total = fields.Float(string='Total', compute='_compute_total', store=True)
    date = fields.Date(string='Fecha', default=datetime.today(), tracking=True)
    license_ids = fields.Many2many('license.license', string='Licencias', tracking=True)

    ot_number = fields.Char(string='OT', tracking=True)
    planta = fields.Char(string='Planta', tracking=True)
    supervisor_planta_id = fields.Many2one('supervisor.area', string='Supervisor de Planta', tracking=True)
    manage_via_or = fields.Boolean(string='Gestionar mediante OR', default=False, tracking=True)
    descripcion_servicio = fields.Text(string='Descripción del Servicio', tracking=True)  # Nuevo campo
        
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                if 'disciplina_id' in vals:
                    disciplina = self.env['license.disciplina'].browse(vals['disciplina_id'])
                    sequence = disciplina.sequence_id
                    if sequence:
                        vals['name'] = sequence.next_by_id()
                    else:
                        vals['name'] = _('New')
                else:
                    vals['name'] = _('New')
        return super(PendingService, self).create(vals_list)

    @api.depends('service_line_ids.total')
    def _compute_total(self):
        for service in self:
            service.total = sum(service.service_line_ids.mapped('total'))

    def action_set_to_pending(self):
        for record in self:
            if record.state == 'draft':
                record.state = 'pending'
            else:
                raise ValidationError(_("El servicio debe estar en estado 'Borrador' para pasar a 'Pendiente'."))

    def action_assign(self):
        self.write({'state': 'assigned'})

    def action_cancel(self):
        self.write({'state': 'canceled'})

    def action_set_to_draft(self):
        self.write({'state': 'draft'})
        
    def unlink(self):
        # Eliminar las líneas de servicio asociadas antes de eliminar el servicio pendiente
        self.service_line_ids.unlink()
        return super(PendingService, self).unlink()


class PendingServiceLine(models.Model):
    _name = 'pending.service.line'
    _description = 'Línea de Servicio Pendiente'

    service_id = fields.Many2one('pending.service', string='Servicio Pendiente', required=True)
    product_id = fields.Many2one('product.product', string='Producto', required=True)
    quantity = fields.Float(string='Cantidad', required=True)
    price_unit = fields.Float(string='Precio Unitario', compute='_compute_price_unit', inverse='_inverse_price_unit', store=True)
    total = fields.Float(string='Total', compute='_compute_total', store=True)

    @api.depends('product_id')
    def _compute_price_unit(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
            else:
                line.price_unit = 0.0

    def _inverse_price_unit(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.price_unit

    @api.depends('quantity', 'price_unit')
    def _compute_total(self):
        for line in self:
            line.total = line.quantity * line.price_unit