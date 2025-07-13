from odoo import api, fields, models, _

class Project(models.Model):
    _inherit = 'project.project'

    sale_line_id = fields.Many2one(
        'sale.order.line', 'Sales Order Item', copy=False,
        compute="_compute_sale_line_id", store=True, readonly=False, index='btree_not_null',
        domain="[('is_service', '=', True), ('is_expense', '=', False), ('state', 'in', ['sale', 'done']), ('order_partner_id', '=?', partner_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="Sales order item that will be selected by default on the tasks and timesheets of this project,"
            " except if the employee set on the timesheets is explicitely linked to another sales order item on the project.\n"
            "It can be modified on each task and timesheet entry individually if necessary.")
    sale_order_id = fields.Many2one(string='Sales Order', related='sale_line_id.order_id', help="Sales order to which the project is linked.", store=True)
    
    sub_update_ids = fields.One2many('project.sub.update', 'project_id')
    #tag_id = fields.Many2one('project.tags', 'Especialidad')
    
    sale_actual = fields.Float(string="Subtotal entregado", compute="_sale_actual", store=True)
    sale_total = fields.Float(string="Subtotal de la venta", compute="_sale_total", store=True)
    sale_missing = fields.Float(string="Subtotal faltante", compute="_sale_missing", store=True)
    
    sale_actual_text = fields.Char(string='Subtotal entregado (pesos)', compute='_sale_actual_text', store=True)
    sale_total_text = fields.Char(string='Subtotal de la venta (pesos)', compute='_sale_total_text', store=True)
    sale_missing_text = fields.Char(string='Subtotal faltante (pesos)', compute='_sale_missing_text', store=True)
    
    state = fields.Selection(string="Estado de la venta", selection=[
            ('draft', "Quotation"),
            ('sent', "Quotation Sent"),
            ('sale', "Sales Order"),
            ('done', "Locked"),
            ('cancel', "Cancelled"),
        ], related="sale_order_id.state", store=True)

    cliente = fields.Many2one(string="Cliente", related='sale_line_id.order_id.partner_id')
    invoiced = fields.Float(string="Facturado", compute="_invoiced", store=True)
    #equipo de venta en revision
    team_id = fields.Many2one(string="Sales Team", related="sale_order_id.team_id", store=True)

    """
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _updatestatus(self):
        current_project_id = self.id
        # Utiliza el ID del proyecto actual según sea necesario
        # Por ejemplo, puedes buscar las tareas relacionadas con el proyecto actual
        for task in tasks
            print(task.id)
    """    

    @api.depends('sale_line_id.qty_invoiced')
    def _invoiced(self):
        for u in self:
            sale = u.env['project.task'].search([('project_id.id', '=', u.id)]).mapped('invoiced')
            u.invoiced = sum(sale)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_actual(self):
        for u in self:
            sale = u.env['project.update'].search([('project_id.id', '=', u.id)]).mapped('sale_current')
            u.sale_actual = sum(sale)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_total(self):
        for u in self:
            sale = u.env['project.task'].search([('project_id.id', '=', u.id)]).mapped('price_subtotal')
            u.sale_total = sum(sale)
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_missing(self):
        for u in self:
            sale = u.sale_total - u.sale_actual
            u.sale_missing = sale
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_actual_text(self):
        for u in self:
            sale = "%.2f" % u.sale_actual
            value_len = sale.find('.')
            for i in range(value_len, 0, -1):
                sale = sale[:i] + ',' + sale[i:] if (value_len-i) % 3 == 0 and value_len != i else sale
            u.sale_actual_text = '$' + sale
    
    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_total_text(self):
        for u in self:
            sale = "% .2f" % u.sale_total
            value_len = sale.find('.')
            for i in range(value_len, 0, -1):
                sale = sale[:i] + ',' + sale[i:] if (value_len-i) % 3 == 0 and value_len != i else sale
            u.sale_total_text = '$' + sale

    @api.depends('sub_update_ids', 'sub_update_ids.unit_progress', 'sub_update_ids.task_id')
    def _sale_missing_text(self):
        for u in self:
            sale = "% .2f" % u.sale_missing
            value_len = sale.find('.')
            for i in range(value_len, 0, -1):
                sale = sale[:i] + ',' + sale[i:] if (value_len-i) % 3 == 0 and value_len != i else sale
            u.sale_missing_text = '$' + sale

    """def _compute_invoice_count(self):
        query = self.env['account.move.line']._search([('move_id.move_type', 'in', ['out_invoice', 'out_refund'])])
        query.add_where('analytic_distribution ?| %s', [[str(project.analytic_account_id.id) for project in self]])
        query.order = None
        query_string, query_param = query.select(
            'jsonb_object_keys(account_move_line.analytic_distribution) as account_id',
            'COUNT(DISTINCT move_id) as move_count',
        )
        query_string = f"{query_string} GROUP BY jsonb_object_keys(account_move_line.analytic_distribution)"
        self._cr.execute(query_string, query_param)
        data = {int(row.get('account_id')): row.get('move_count') for row in self._cr.dictfetchall()}
        for project in self:
            project.invoice_count = data.get(project.analytic_account_id.id, 0)
        res = super(Project, self)._compute_invoice_count()
        return res"""

    def action_view_avances(self):
        return {
            'name': _("Avances de Proyecto"),
            'type': 'ir.actions.act_window',
            'res_model': 'project.sub.update',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
            },
            'target': 'current',
        }

