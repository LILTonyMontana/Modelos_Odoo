from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ProjectSubUpdateWizard(models.TransientModel):
    _name = 'project.sub.update.wizard'
    _description = 'Wizard para gestión de avances de proyecto'

    project_id = fields.Many2one(
        'project.project',
        string='Proyecto'
    )

    project_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analítica de Proyecto',
        related='project_id.analytic_account_id',
    )

    update_id = fields.Many2one(
        'project.update', 
        string='Actualización', 
        ondelete='cascade',
        domain="[('project_id', '=?', project_id)]"
    )

    project_partner_id = fields.Many2one(
        related='project_id.partner_id', 
        store=True
    )

    sub_update_id = fields.Many2one(
        'project.sub.update',
        string='Avances disponibles',
        domain="[('project_id', '=', False), ('update_id', '=', False), ('cliente_ct', '=', project_partner_id)]",
        required=True
    )

    provisional_analitica = fields.Many2one(
        'account.analytic.account',
        string='Analítica Provisional',
        related='sub_update_id.provisional_analytic',
    )

    oc_pedido = fields.Char(
        string='OC Pedido',
        related='project_id.sale_order_id.name',
        readonly=False
    )

    @api.onchange('update_id')
    def _onchange_update_id(self):
        if self.update_id and self.update_id.project_id:
            self.project_id = self.update_id.project_id

    def action_add_sub_updates(self):
        self.ensure_one()
        
        # Manejo de transferencia analítica
        if self.sub_update_id.provisional_analytic and self.project_id.analytic_account_id:        
            return self._open_analytic_transfer_wizard()
        
        return self._finalize_sub_update_addition()
    
    def _open_analytic_transfer_wizard(self):
        return {
            'name': _('Transferir Analítica'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sub_update_id': self.sub_update_id.id,
                'default_destination_analytic_id': self.project_id.analytic_account_id.id,
                'default_project_destination_id': self.project_id.id,
                'origin_wizard_id': self.id,
                'origin_project_id': self.project_id.id,
                'origin_oc_pedido': self.oc_pedido,
                'origin_update_id': self.update_id.id if self.update_id else False,
            }
        }
    
    def _finalize_sub_update_addition(self):
        """Proceso final para agregar avances"""
        # Usar la actualización seleccionada o encontrar una existente
        update = self._get_or_create_update()
        
        # Asignar el avance
        self._assign_sub_update(update)
        
        # Asignar tarea si es necesario
        self._assign_task_if_needed()
        
        return {'type': 'ir.actions.act_window_close'}

    def _get_or_create_update(self):
        """Obtiene o crea la actualización del proyecto"""
        if self.update_id:
            return self.update_id
            
        # Buscar última actualización no cerrada del proyecto
        update = self.env['project.update'].search([
            ('project_id', '=', self.project_id.id),
            ('status', '!=', 'closed')
        ], order='create_date desc', limit=1)
        
        return update or self.env['project.update'].create({
            'project_id': self.project_id.id,
        })

    def _assign_sub_update(self, update):
        """Asigna el avance a la actualización"""
        self.sub_update_id.write({
            'update_id': update.id,
            'project_id': self.project_id.id,
            'oc_pedido': self.oc_pedido,
        })

    def _assign_task_if_needed(self):
        """Asigna tarea automáticamente si no existe"""
        if not self.sub_update_id.task_id and self.sub_update_id.producto:
            task = self._find_or_create_task()
            if task:
                self.sub_update_id.task_id = task.id

    def _find_or_create_task(self):
        """Busca o crea tarea compatible con el producto del avance"""
        # 1. Buscar por producto en orden de venta del proyecto
        if self.project_id.sale_order_id:
            sale_line = self.env['sale.order.line'].search([
                ('order_id', '=', self.project_id.sale_order_id.id),
                ('product_id', '=', self.sub_update_id.producto.product_variant_id.id),
                ('task_id', '!=', False)
            ], limit=1)
            if sale_line and sale_line.task_id:
                return sale_line.task_id
        
        # 2. Buscar por nombre de producto en tareas existentes
        task = self.env['project.task'].search([
            ('project_id', '=', self.project_id.id),
            ('name', '=ilike', self.sub_update_id.producto.name)
        ], limit=1)
        
        # 3. Crear nueva tarea si no existe
        if not task:
            task = self.env['project.task'].create({
                'name': self.sub_update_id.producto.name,
                'project_id': self.project_id.id,
                'total_pieces': self.sub_update_id.unit_progress or 0
            })
        
        return task

    @api.depends("project_id.sale_order_id.tag_ids")
    def _compute_disciplina(self):
        for record in self:
            if record.project_id and record.project_id.sale_order_id:
                record.disciplina = [(6, 0, record.project_id.sale_order_id.tag_ids.ids)]
            else:
                record.disciplina = [(5, 0, 0)]