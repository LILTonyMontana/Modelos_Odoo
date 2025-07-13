from odoo import fields, models, api
from odoo.exceptions import ValidationError


class Task(models.Model):
    _inherit = 'project.task'
    
    sale_line_id = fields.Many2one(
        'sale.order.line', 'Sales Order Item', copy=False,
        compute="_compute_sale_line_id", store=True, readonly=False, index='btree_not_null',
        domain="[('is_service', '=', True), ('is_expense', '=', False), ('state', 'in', ['sale', 'done']), ('order_partner_id', '=?', partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Sales order item that will be selected by default on the tasks and timesheets of this project,"
            " except if the employee set on the timesheets is explicitely linked to another sales order item on the project.\n"
            "It can be modified on each task and timesheet entry individually if necessary.")
    sale_order_id = fields.Many2one(string='Sales Order', related='sale_line_id.order_id', help="Sales order to which the project is linked.")
    
    delivered = fields.Float(string='Entregado', related='sale_line_id.qty_delivered')
    price_unit = fields.Float(string='Precio', related='sale_line_id.price_unit')
    total_pieces = fields.Float(string="Unidades (decimal)", related="sale_line_id.product_uom_qty")
    price_subtotal = fields.Float(string='Subtotal', compute='_subtotal')
    qty_invoiced = fields.Float(string="Facturado (unidades)", related="sale_line_id.qty_invoiced", store=True)
    disc =fields.Many2one(string='Especialidad', related='sale_line_id.product_id.categ_id', store=True)
    invoiced = fields.Float(string="Facturado", compute="_invoiced", store=True)
    
    sub_update_ids = fields.One2many('project.sub.update', 'task_id', 
                                      domain="[('project_id', '=', project_id), ('task_id.id', '=', id)]", string='Actualización de tareas')
    sub_update = fields.Many2one('project.sub.update', compute="_last_update", store=True)
    last_update = fields.Many2one('project.update', related='sub_update.update_id', string='Última actualización')
    sub_d_update = fields.Many2one('project.sub.update', compute="_d_update", string='Última actualización de tarea', store=True)
    last_d_update = fields.Many2one('project.update', related='sub_d_update.update_id', string='Última actualización modificada')
    last_update_date = fields.Datetime(related='last_d_update.write_date', string = 'Modificado por ult. vez')
    
    quant_progress = fields.Float(string="Piezas/Servicio", compute="_units", store=True)
    progress = fields.Integer(compute="_progress", string="Progreso", store=True)
    progress_percentage = fields.Float(compute="_progress_percentage", string="Progreso porcentual", store=True)
    
    is_complete = fields.Boolean(string="Complete", compute="_is_complete", default=False, store=True)


    @api.depends('sale_line_id.qty_invoiced')
    def _invoiced(self):
        for u in self:
            u.invoiced = u.qty_invoiced * u.price_unit
    
    @api.model
    def _d_update(self):
        for u in self:
            u.sub_d_update = u.env['project.sub.update'].search([('project_id.id', '=', u.project_id.id), ('task_id.id', '=', u.id)], limit=1)
    
    @api.model
    def _check_to_recompute(self):
        return[id]
    
    @api.depends('sub_update_ids')
    def _last_update(self):
        for u in self:
            if not u.id:
                continue
            u.sub_update = u.env['project.sub.update'].search([('project_id.id', '=', u.project_id.id), ('task_id.id', '=', u.id)], order='id desc', limit=1)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'project_id.update_ids')
    def _units(self):
        for u in self:
            # Verifica si el registro está siendo creado (i.e., no tiene ID aún)
            if not u.id:
                continue
            
            progress = u.env['project.sub.update'].search([
                ('project_id.id', '=', u.project_id.id),
                ('task_id.id', '=', u.id)
            ]).mapped('unit_progress')
            
            u.quant_progress = sum(progress)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'project_id.update_ids')
    def _progress(self):
        for u in self:
            if u.total_pieces > 0:
                progress = (u.quant_progress / u.total_pieces) * 100
            else:
                progress = 0
            u.progress = int(progress)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'project_id.update_ids')
    def _progress_percentage(self):
        for u in self:
            # Verifica si el registro está siendo creado (i.e., no tiene ID aún)
            if not u.id:
                continue
            u.progress_percentage = u.progress / 100
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'project_id.update_ids')
    def _subtotal(self):
        for u in self:
            if not u.id:
                continue
            subtotal = u.env['sale.order.line'].search([('id', '=', u.sale_line_id.id)]).mapped('price_subtotal')
            if subtotal:
                u.price_subtotal = float(subtotal[0])
            else:
                u.price_subtotal = 0.0

    """"
    CODIGO ORIGINAL
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress')
    def _is_complete(self):
        for u in self:
            if u.quant_progress == u.total_pieces:
                
                u.is_complete = True
            else:
                u.is_complete = False


    #EN EVALUACION PARA GESTION AUTOMATICA DE TAREAS EN BASE A SU AVANCE
    #CAMBIA EL ESTATUSO PERO ASIGNA LA PRIMER ETAPA Y NECESITAMOS ASIGANR LA ETAPA CORRESPONDIENTE A LAS TAREAS DEL PROYECTO
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress')
    def _is_complete(self):
        for task in self:
            if task.quant_progress == task.total_pieces:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id.name = "Listo"
            elif task.quant_progress > 0:
                task.is_complete = False
                task.stage_id.name = "En progreso"
                task.state = "01_in_progress"
            else:
                task.is_complete = False
                task.stage_id.name = "En espera"
                task.state = "04_waiting_normal"


    #EN ESTA VERSION YA SE ESTA BUSCANDO CON PROJECT.TASK.TYPE, PERO HACE FALTA ELEGIR DENTRO DE LOS PROJECT_IDS               
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress')
    def _is_complete(self):
        for task in self:
            if task.quant_progress == task.total_pieces:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id = self.env['project.task.type'].search([('name', '=', 'Listo')], limit=1)
            elif task.quant_progress > 0:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([('name', '=', 'En progreso')], limit=1)
                task.state = "01_in_progress"
            else:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([('name', '=', 'Pendientes')], limit=1)
                task.state = "04_waiting_normal"
                """

    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress')
    def _is_complete(self):
        
        for task in self:
            if task.total_pieces == 0:

                continue
                
            if task.quant_progress == task.total_pieces:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'Listo'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
            elif task.quant_progress > 0:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'En progreso'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
                task.state = "01_in_progress"
            else:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'Pendientes'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
                task.state = "04_waiting_normal"


    @api.model
    def update_task_status(self):
        tasks = self.env['project.task'].search([("sale_order_id", "!=", False)])
        for task in tasks:
            if task.quant_progress == task.total_pieces:
                task.is_complete = True
                task.state = "1_done"
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'Listo'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
            elif task.quant_progress > 0:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'En progreso'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
                task.state = "01_in_progress"
            else:
                task.is_complete = False
                task.stage_id = self.env['project.task.type'].search([
                    ('name', '=', 'Pendientes'),
                    ('project_ids', 'in', task.project_id.ids)
                ], limit=1)
                task.state = "04_waiting_normal"

    
    
    @api.constrains('sub_update_ids')
    def _check_unique_items(self):
        for record in self:
            item_ids = record.item_ids.mapped('sub_update_ids')
            if len(item_ids) != len(set(item_ids)):
                raise ValidationError('No se pueden agregar ítems duplicados.')
