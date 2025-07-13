from odoo import fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime

class ProjectUpdate(models.Model):
    _inherit = "project.update"
    _order = "date desc"

    # Campos requeridos con valores por defecto
    """
    name = fields.Char(
        string='Nombre de Actualización',
        required=True,
        default=lambda self: self._generate_sequence(),
        tracking=True,
        copy=False
    )
    
    def _generate_sequence(self):
        prefix = 'Avance'
        sequence = self.env['ir.sequence'].next_by_code('project.update.sequence') or '0001'
        return f"{prefix}{sequence}"
    """
    
    status = fields.Selection(
        [
            ('on_track', 'En Camino'),
            ('at_risk', 'En Riesgo'),
            ('off_track', 'Fuera de Camino'),
            ('on_hold', 'En Espera'),
            ('closed', 'Cerrado')
        ],
        string='Estado',
        required=True,
        default='on_track'
    )
    
    sub_update_ids = fields.One2many(
        "project.sub.update", "update_id", string="Creación De Avances"
    )

    def action_add_sub_updates(self):
        self.ensure_one()
        
        # Buscar la última actualización del proyecto que no esté cerrada
        update = self.env["project.update"].search([
            ("project_id", "=", self.project_id.id),
            ("status", "!=", "closed")
        ], order="create_date desc", limit=1)
        
        # Si no existe una actualización abierta, crear una nueva
        if not update:
            update = self.env["project.update"].create({
                "project_id": self.project_id.id,
                "status": "on_track"
            })
        
        # Asignar todos los avances a esta actualización
        for sub in self.sub_update_ids:
            # Si el avance ya está asignado a otra actualización, saltarlo
            if sub.update_id and sub.update_id != update:
                continue
                
            sub.write({
                'update_id': update.id,
                'project_id': self.project_id.id
            })
            
            # Asignar tarea automáticamente si no tiene
            if not sub.task_id and sub.producto:
                task = self._find_or_create_task(sub)
                sub.task_id = task.id
        
        # Forzar el cálculo de los campos relacionados
        update._compute_sale_fields()
        
        return {
            'type': 'ir.actions.act_window_close',
            'context': {'default_update_id': update.id}  # Para próximas operaciones
        }

    def _find_or_create_task(self, sub_update):
        """Encuentra o crea tarea compatible con el producto del avance"""
        # 1. Buscar tarea existente
        task = self.env["project.task"].search([
            ("project_id", "=", sub_update.project_id.id),
            "|",
            ("name", "=ilike", sub_update.producto.name),
            ("sale_line_id.product_id", "=", sub_update.producto.product_variant_id.id)
        ], limit=1)
        
        # 2. Crear nueva tarea si no existe
        if not task:
            task = self.env["project.task"].create({
                "name": sub_update.producto.name,
                "project_id": sub_update.project_id.id,
                "sale_line_id": False,  # No vinculada a orden de venta
                "total_pieces": sub_update.unit_progress  # Inicializar con el primer avance
            })
        # 3. Para tareas existentes sin orden de venta, actualizar total_pieces si es necesario
        elif not task.sale_line_id:
            if task.total_pieces < sub_update.unit_progress:
                task.total_pieces = sub_update.unit_progress
        
        return task
        
    sale_current = fields.Float(
        string="Avance del subtotal", compute="_sale_current", store=True, default=0.0
    )
    sale_actual = fields.Float(
        string="Subtotal entregado", compute="_sale_actual", store=True, default=0.0
    )
    sale_total = fields.Float(
        string="Subtotal de la venta", compute="_sale_total", store=True, default=0.0
    )
    sale_missing = fields.Float(
        string="Subtotal faltante", compute="_sale_missing", store=True, default=0.0
    )

    sale_current_text = fields.Char(
        string="Avance del subtotal (pesos)", compute="_sale_current_text", store=True
    )
    sale_actual_text = fields.Char(
        string="Subtotal entregado (pesos)", compute="_sale_actual_text", store=True
    )
    sale_total_text = fields.Char(
        string="Subtotal de la venta (pesos)", compute="_sale_total_text", store=True
    )
    sale_missing_text = fields.Char(
        string="Subtotal faltante (pesos)", compute="_sale_missing_text", store=True
    )

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_current(self):
        for u in self:
            sale = (
                u.env["project.sub.update"]
                .search([("update_id.id", "=", u._origin.id)])
                .mapped("sale_current")
            )
            u.sale_current = sum(sale)

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_actual(self):
        for u in self:
            sale = (
                u.env["project.update"]
                .search(
                    [
                        ("project_id.id", "=", u.project_id.id),
                        ("id", "<=", u._origin.id),
                    ]
                )
                .mapped("sale_current")
            )
            u.sale_actual = sum(sale)

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_total(self):
        for u in self:
            sale = (
                u.env["project.task"]
                .search([("project_id.id", "=", u.project_id.id)])
                .mapped("price_subtotal")
            )
            u.sale_total = sum(sale)

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_missing(self):
        for u in self:
            sale = u.sale_total - u.sale_actual
            u.sale_missing = sale

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_current_text(self):
        for u in self:
            sale = "%.2f" % u.sale_current
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_current_text = "$" + sale

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_actual_text(self):
        for u in self:
            sale = "%.2f" % u.sale_actual
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_actual_text = "$" + sale

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_total_text(self):
        for u in self:
            sale = "%.2f" % u.sale_total
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_total_text = "$" + sale

    @api.depends(
        "sub_update_ids", "sub_update_ids.unit_progress", "sub_update_ids.task_id"
    )
    def _sale_missing_text(self):
        for u in self:
            sale = "%.2f" % u.sale_missing
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_missing_text = "$" + sale

    """
    def write(self, vals):
        res = super().write(vals)
        if "sub_update_ids" in vals:
            for update in self:
                for sub in update.sub_update_ids:
                    # Asignar update_id si no tiene
                    if not sub.update_id:
                        sub.update_id = update.id

                    # Asignar project_id si no tiene
                    if not sub.project_id:
                        sub.project_id = update.project_id.id

                    # Buscar y asignar tarea basada en el nombre del producto
                    if not sub.task_id and sub.producto:  # Asegurar que hay un producto
                        task = self.env["project.task"].search(
                            [
                                ("name", "=", sub.producto.name),
                                ("project_id", "=", sub.project_id.id),
                            ],
                            limit=1,
                        )
                        if task:
                            sub.task_id = task.id
        return res
    """

    # Metodo para validación de Cliente CT corresponda con Cliente Planta, Area, Supervisor Cliente
    planta_domain = fields.Char(compute='_compute_domains')
    area_domain = fields.Char(compute='_compute_domains')
    supervisor_domain = fields.Char(compute='_compute_domains')
    @api.depends('sub_update_ids.ct.cliente')  # Si ct está en project.sub.update
    def _compute_domains(self):
        for record in self:
            # Obtener el primer registro de ct de los sub updates
            ct_record = record.sub_update_ids and record.sub_update_ids[0].ct
            if ct_record and ct_record.cliente:
                domain = [('cliente', '=', ct_record.cliente.id)]
                domain_str = str(domain)
            else:
                domain_str = str([('id', '=', False)])
            
            record.planta_domain = domain_str
            record.area_domain = domain_str
            record.supervisor_domain = domain_str

            # Limpieza de campos si no coinciden
            if (record.planta and record.planta.cliente != (ct_record and ct_record.cliente)):
                record.planta = False
            if (record.area_id and record.area_id.cliente != (ct_record and ct_record.cliente)):
                record.area_id = False
            if (record.supervisorplanta and record.supervisorplanta.cliente != (ct_record and ct_record.cliente)):
                record.supervisorplanta = False