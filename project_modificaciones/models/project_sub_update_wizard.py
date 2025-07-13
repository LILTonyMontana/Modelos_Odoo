from odoo import fields, models, api, _
from odoo.exceptions import UserError

class ProjectSubUpdateWizard(models.TransientModel):
    _name = 'project.sub.update.wizard'
    _description = 'Wizard para gestión de avances de proyecto'

    project_id = fields.Many2one(
        'project.project',
        string='Proyecto',
        #required=True
    )

    project_analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analítica de Proyecto',
        related='project_id.analytic_account_id',
    )

    update_id = fields.Many2one(
        'project.update', 
        string='Actualización', 
        ondelete='cascade'
    )

    project_partner_id = fields.Many2one(related='project_id.partner_id', store=True)


    sub_update_id = fields.Many2one(
        'project.sub.update',
        string='Avances disponibles',
        domain="[('project_id', '=', False), ('update_id', '=', False), ('cliente_ct', '=', project_partner_id)]",  # Filtro clave
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
        #Actualiza el project_id cuando se selecciona una actualización
        if self.update_id and self.update_id.project_id:
            self.project_id = self.update_id.project_id

    def action_add_sub_updates(self):
        self.ensure_one()
        # Verificar si necesita transferencia analítica
        if self.sub_update_id.provisional_analytic and self.project_id.analytic_account_id:        
            # Abrir directamente el wizard de transferencia analítica    
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
                    'origin_wizard_id': self.id,  # Guardamos referencia al wizard original
                    'origin_project_id': self.project_id.id,
                    'origin_oc_pedido': self.oc_pedido,
                    'origin_update_id': self.update_id.id if self.update_id else False,
                }
            }
        
        # Si no necesita transferencia, continuar con el proceso normal
        return self._finalize_sub_update_addition()
    
    def _finalize_sub_update_addition(self):
        """Proceso final de agregar el avance"""
        # Buscar o crear la actualización del proyecto
        update = self.update_id or self.env['project.update'].search(
            [('project_id', '=', self.project_id.id)],
            order='create_date desc',
            limit=1
        )
        
        if not update:
            update = self.env['project.update'].create({
                'project_id': self.project_id.id,
            })
        
        # Preparar valores para actualizar el avance
        update_vals = {
            'update_id': update.id,
            'project_id': self.project_id.id,
            'oc_pedido': self.oc_pedido,
        }
        
        # Actualizar el avance
        self.sub_update_id.write(update_vals)
        
        # Asignar tarea automáticamente si no existe
        for sub in self.sub_update_id:
            if not sub.task_id and sub.producto:
                task = self.env['project.task'].search([
                    ('name', 'like', f"%{sub.producto.name}"),
                    ('project_id', '=', self.project_id.id)
                ], limit=1)
                if task:
                    sub.task_id = task.id
        
        return {
            'type': 'ir.actions.act_window_close',
        }


    """
    def open_transfer_wizard(self):
        self.ensure_one()
        if not self.sub_update_id.provisional_analytic:
            raise UserError("El avance no tiene cuenta analítica provisional asignada.")
        
        return {
            'name': _('Transferir Analítica'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sub_update_id': self.sub_update_id.id,
            }
        }
    """

    @api.depends("project_id.sale_order_id.tag_ids")
    def _compute_disciplina(self):
        #Carga etiquetas de disciplina desde la orden de venta
        for record in self:
            if record.project_id and record.project_id.sale_order_id:
                record.disciplina = [(6, 0, record.project_id.sale_order_id.tag_ids.ids)]
            else:
                record.disciplina = [(5, 0, 0)]
