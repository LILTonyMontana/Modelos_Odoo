from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AnalyticTransferWizard(models.TransientModel):
    _name = 'analytic.transfer.wizard'
    _description = 'Asistente para Transferencia de Analíticas Provisionales'
    
    sub_update_id = fields.Many2one(
        'project.sub.update',
        string='Avance Físico',
        required=True,
        default=lambda self: self._context.get('active_id')
    )
    
    origin_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analítica Provisional',
        readonly=True,
        related='sub_update_id.provisional_analytic'
    )
    
    destination_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analítica Oficial',
        required=True,
        #domain="[('plan_id.name', '!=', 'AVANCES SIN O/V')]"
    )
    
    project_destination_id = fields.Many2one(
        'project.project',
        string='Proyecto Destino',
        domain="[('analytic_account_id', '=', destination_analytic_id)]"
    )
    
    # Campos computados para documentos relacionados
    purchase_orders = fields.One2many(
        'purchase.order',
        compute='_compute_related_docs',
        string='Órdenes de Compra'
    )
    
    stock_pickings = fields.One2many(
        'stock.picking',
        compute='_compute_related_docs',
        string='Mov. Almacen'
    )
    
    account_moves = fields.One2many(
        'account.move',
        compute='_compute_related_docs',
        string='Facturas'
    )
    
    timesheets = fields.One2many(
        'account.analytic.line',
        compute='_compute_related_docs',
        string='Hojas de Horas'
    )
    
    hr_expenses = fields.One2many(
        'hr.expense',
        compute='_compute_related_docs',
        string='Gastos'
    )

    @api.depends('origin_analytic_id')
    def _compute_related_docs(self):
        for wizard in self:
            analytic_id = wizard.origin_analytic_id.id
            if not analytic_id:
                wizard.purchase_orders = False
                wizard.stock_pickings = False
                wizard.account_moves = False
                wizard.timesheets = False
                wizard.hr_expenses = False
                continue
            
            # Búsqueda exacta por ID analítico
            wizard.purchase_orders = self.env['purchase.order'].search([
                ('order_line.analytic_distribution', 'in', [analytic_id])
            ])
            
            wizard.stock_pickings = self.env['stock.picking'].search([
                ('move_ids.analytic_distribution', 'in', [analytic_id])
            ])
            
            wizard.account_moves = self.env['account.move'].search([
                ('line_ids.analytic_distribution', 'in', [analytic_id])
            ])
            
            wizard.timesheets = self.env['account.analytic.line'].search([
                ('project_id', '=', analytic_id)
            ])
            
            wizard.hr_expenses = self.env['hr.expense'].search([
                ('analytic_distribution', 'in', [analytic_id])
            ])

    def action_transfer_analytic(self):
        self.ensure_one()
        
        if not self.origin_analytic_id or not self.destination_analytic_id:
            raise UserError(_("Debe seleccionar ambas cuentas analíticas"))
        
        if self.origin_analytic_id == self.destination_analytic_id:
            raise UserError(_("No puede transferir a la misma cuenta analítica"))

        try:
            with self.env.cr.savepoint():
                # Transferir documentos relacionados
                transfer_results = {
                    'purchase_orders': self._transfer_relation('purchase.order', 'order_line'),
                    'stock_pickings': self._transfer_relation('stock.picking', 'move_ids'),
                    'account_moves': self._transfer_relation('account.move', 'line_ids'),
                    'timesheets': self._transfer_timesheets(),
                    'hr_expenses': self._transfer_relation('hr.expense', None)
                }
                
                # Actualizar el avance físico
                self.sub_update_id.write({
                    'provisional_analytic': False,
                    'analytic_distribution': {str(self.destination_analytic_id.id): 100.0}
                })
                
                # Desactivar analítica provisional
                self.origin_analytic_id.unlink()
                
                # Registrar mensaje
                message = self._prepare_transfer_message(transfer_results)
                self.sub_update_id.message_post(body=message)

                # Después de completar la transferencia exitosamente
                if self._context.get('origin_wizard_id'):
                    # Recuperar el wizard original y finalizar el proceso
                    origin_wizard = self.env['project.sub.update.wizard'].browse(
                        self._context['origin_wizard_id'])
                    
                    return origin_wizard._finalize_sub_update_addition()
                
                # Si no viene de un wizard original, mostrar notificación
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Transferencia Exitosa'),
                        'message': _("""
                            Se completó la transferencia analítica:
                                Órdenes de compra: %d
                                Mov. Almacen: %d
                                Facturas: %d
                                Hojas de horas: %d
                                Gastos: %d
                        """) % (
                            transfer_results['purchase_orders'],
                            transfer_results['stock_pickings'],
                            transfer_results['account_moves'],
                            transfer_results['timesheets'],
                            transfer_results['hr_expenses']
                        ),
                        'sticky': False,
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }
                
        except Exception as e:
            _logger.error("Error en transferencia analítica: %s", str(e), exc_info=True)
            raise UserError(_("Error durante la transferencia: %s") % str(e))

    def _mark_expenses_as_editable(self, expenses):
        """Marcar gastos y reportes como editables temporalmente"""
        for expense in expenses:
            expense.is_editable = True
            if expense.sheet_id:
                expense.sheet_id.is_editable = True
    
    def _restore_expenses_editable_state(self, expenses):
        """Restaurar el estado editable original"""
        for expense in expenses:
            expense.is_editable = False
            if expense.sheet_id:
                expense.sheet_id.is_editable = False
    
    def _update_sheet_lines_distribution(self, sheet, origin, destination):
        """Actualizar distribución analítica en líneas de reporte"""
        for line in sheet.expense_line_ids:
            if origin in str(line.analytic_distribution):
                dist = line.analytic_distribution
                new_dist = {}
                for key, perc in dist.items():
                    ids = key.split(',')
                    ids_updated = [destination if id == origin else id for id in ids]
                    new_dist[','.join(ids_updated)] = perc
                line.analytic_distribution = new_dist
                
    def _transfer_relation(self, model_name, line_field):
        origin = str(self.origin_analytic_id.id)
        destination = str(self.destination_analytic_id.id)
        updated = 0
    
        related_records = {
            'purchase.order': self.purchase_orders,
            'stock.picking': self.stock_pickings,
            'account.move': self.account_moves,
            'hr.expense': self.hr_expenses
        }.get(model_name, self.env[model_name])
    
        if model_name == 'hr.expense':
            self._mark_expenses_as_editable(related_records)
    
        try:
            for record in related_records:
                if line_field:
                    for line in record[line_field]:
                        if line.analytic_distribution and origin in str(line.analytic_distribution):
                            if isinstance(line.analytic_distribution, dict):
                                new_dist = {}
                                for key, perc in line.analytic_distribution.items():
                                    ids = key.split(',')
                                    ids_updated = [destination if id == origin else id for id in ids]
                                    new_dist[','.join(ids_updated)] = perc
                                #line.analytic_distribution = new_dist
                                line.write({'analytic_distribution': new_dist})
                            else:
                                line.analytic_distribution = str(line.analytic_distribution).replace(origin, destination)
                            updated += 1
                else:
                    if record.analytic_distribution and origin in str(record.analytic_distribution):
                        if isinstance(record.analytic_distribution, dict):
                            new_dist = {}
                            for key, perc in record.analytic_distribution.items():
                                ids = key.split(',')
                                ids_updated = [destination if id == origin else id for id in ids]
                                new_dist[','.join(ids_updated)] = perc
                            record.analytic_distribution = new_dist
                        else:
                            record.analytic_distribution = str(record.analytic_distribution).replace(origin, destination)
                        updated += 1
    
                        # Si tiene reporte, actualiza líneas del sheet:
                        if model_name == 'hr.expense' and record.sheet_id:
                            self._update_sheet_lines_distribution(record.sheet_id, origin, destination)
    
        finally:
            if model_name == 'hr.expense':
                self._restore_expenses_editable_state(related_records)
    
        return updated

    def _transfer_timesheets(self):
        """Transferir hojas de horas"""
        if not self.timesheets:
            return 0
            
        return self.timesheets.write({
            'account_id': self.destination_analytic_id.id,
            'project_id': self.project_destination_id.id if self.project_destination_id else False
        })

    def _prepare_transfer_message(self, results):
        """Preparar mensaje para el chatter"""
        return _("""
            Transferencia analítica completada
                Origen:%s
                Destino:%s
            Documentos transferidos:
                Órdenes de compra actualizadas: %d
                Mov. Almacen actualizados: %d
                Facturas actualizadas: %d
                Hojas de horas transferidas: %d
                Gastos actualizados: %d
        """) % (
            self.origin_analytic_id.name,
            self.destination_analytic_id.name,
            results['purchase_orders'],
            results['stock_pickings'],
            results['account_moves'],
            results['timesheets'],
            results['hr_expenses']
        )