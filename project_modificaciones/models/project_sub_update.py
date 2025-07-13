from odoo import fields, models, api, _
from datetime import datetime, date
from odoo.exceptions import ValidationError, UserError
from random import randint
import json
import logging

_logger = logging.getLogger(__name__)


class ProjectSubUpdate(models.Model):
    _name = "project.sub.update"
    _description = "Avances fisicos"
    _order = "date desc"
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]

    state = fields.Selection(
        [
            ("no_fact", "No facturado"),
            ("fact", "Facturado"),
            ("inc", "Incobrable"),
        ],
        string="Estado",
        copy=False,
        default="no_fact",
        tracking=True,
    )
    # Bandera
    edit_mode = fields.Boolean(string="Modo Edición", default=False)

    # Metodo para cambiar el estado.
    def toggle_edit_mode(self):
        for record in self:
            record.edit_mode = not record.edit_mode
        return True

    # Identificador
    name = fields.Char(
        string="ID Avance",
        copy=False,
        default=lambda self: _("Nuevo"),
        readonly=True,
        index=True,
        tracking=True,
    )
    # Usuario
    created_by = fields.Many2one(
        comodel_name="res.users",
        string="Avance Creado Por",
        default=lambda self: self.env.user,
        readonly=True,
        tracking=2,
    )
    # Datos del Servicio
    project_id = fields.Many2one(
        "project.project",
        string="Proyecto",
        store=True,
        help="Proyecto Elaborado A Partir De La Orden De Venta",
        tracking=True,
    )  # related='update_id.project_id'

    # Metodo Para Agregar ID_Project
    @api.onchange("update_id")
    def _onchange_update_id(self):
        if self.update_id and self.update_id.project_id:
            self.project_id = self.update_id.project_id

    avance_project_id = fields.Many2one(
        "avance.project",
        string="Actualización",
        ondelete="cascade",
        help="Actualizaciones Del Proyecto A Trabajar",
        tracking=True,
    )

    update_id = fields.Many2one(
        "project.update",
        string="Actualización",
        ondelete="cascade",
        help="Actualizaciones Del Proyecto A Trabajar",
        tracking=True,
    )
    
    task_id = fields.Many2one(
        "project.task",
        domain="[('project_id', '=', project_id), ('is_complete', '=', False)]",
        string="Tarea",
        help="Tarea Del Proyecto (Aqui Vera La Tarea En La Cual El Avance Estara Relacionado)",
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente (Alias)",
        compute="_compute_partner_id",
        store=True,
    )

    @api.depends("cliente_project")
    def _compute_partner_id(self):
        for record in self:
            record.partner_id = record.cliente_project

    cliente_project = fields.Many2one(
        string="Cliente",
        related="project_id.partner_id",
        store=True,
        help="Cliente Al Cual Se Le Va A Proveer El Trabajo",
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Orden De Venta",
        related="project_id.sale_order_id",
        store=True,
        help="Orden De Venta Relacionada Al Trabajo",
        tracking=True,
    )
    disciplina = fields.Many2many(
        "crm.tag",
        # "crm_tag_project_sub_update_rel",
        # "sub_update_id",
        # "tag_id",
        string="Etiquetas",
        compute="_compute_disciplina",
        store=True,
        help="Etiqueta del Trabajo",
        tracking=True,
    )

    # Metodo Para Cargar Todas Las Etiquetas Relacionadas Con El Proyecto (Orden De Servicio)
    @api.depends("project_id.sale_order_id.tag_ids")
    def _compute_disciplina(self):
        for record in self:
            if record.project_id and record.project_id.sale_order_id:
                record.disciplina = [
                    (6, 0, record.project_id.sale_order_id.tag_ids.ids)
                ]
            else:
                record.disciplina = [(5, 0, 0)]

    analitica = fields.Many2one(
        "account.analytic.account",
        string="Analitica",
        related="project_id.analytic_account_id",
        help="Cuenta Analítica Enlazada Al Proyecto",
        tracking=True,
    )

    provisional_analytic = fields.Many2one(
        "account.analytic.account",
        string="Cuenta Analítica Provisional",
        #domain="[('is_provisional', '=', True)]",
        help="Cuenta Analítica Provisional Antes De Asignar La O/S"
    )

    #Campo Nuevo de Nuevo de ser Muy Nuevo
    provisional_client = fields.Many2one(
        'res.partner',
        string='Cliente Analitica Provisional',
        compute='_compute_provisional_client',
        store=True
    )

    @api.depends('provisional_analytic')
    def _compute_provisional_client(self):
        for record in self:
            record.provisional_client = record.provisional_analytic.partner_id if record.provisional_analytic else False

    @api.onchange('provisional_analytic')
    def _onchange_provisional_analytic(self):
        if self.provisional_analytic and self.provisional_analytic.partner_id:
            cliente = self.provisional_analytic.partner_id
            
            # Buscar y asignar el primer CT relacionado con este cliente
            ct = self.env['centro.trabajo.avance'].search(
                [('cliente', '=', cliente.id)], limit=1)
            if ct:
                self.ct = ct
                
                # Buscar y asignar la primera planta relacionada
                planta = self.env['planta.avance'].search(
                    [('cliente', '=', cliente.id)], limit=1)
                if planta:
                    self.planta = planta
                    
                    # Buscar y asignar la primera área relacionada
                    area = self.env['area.avance'].search(
                        [('cliente', '=', cliente.id)], limit=1)
                    if area:
                        self.area_id = area
                    
                    # Buscar y asignar el primer supervisor relacionado
                    supervisor = self.env['supervisor.area'].search(
                        [('cliente', '=', cliente.id)], limit=1)
                    if supervisor:
                        self.supervisorplanta = supervisor

    
    #ID Avance
    @api.model_create_multi
    def create(self, vals_list):
       # plan = self.env['account.analytic.plan'].search(
        #    [('name', '=', 'AVANCES SIN O/V')], limit=1)
        #if not plan:
         #   raise UserError("Debe existir un plan analítico llamado 'AVANCE SIN O/V'.")
    
        now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        date_str = now.strftime("%y%m%d%H%M%S")
    
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = f"AV/{date_str}"
    
        records = super().create(vals_list)
    
        #for record in records:
         #   if not record.project_id:
          #      aa = self.env['account.analytic.account'].create({
           #         'name': f'Provisional {record.name}',
            #        'company_id': self.env.company.id,
             #       'plan_id': plan.id,
              #  })
               # record.provisional_analytic = aa
                #record.analytic_distribution = {str(aa.id): 100.0}
    
        return records

    #Wizard analytic
    def open_analytic_transfer_wizard(self):
        return {
            'name': 'Transferir Analítica',
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.transfer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sub_update_id': self.id,
                'default_origin_analytic_id': self.provisional_analytic.id if self.provisional_analytic else False,
            }
        }

    # Datos del Producto
    producto = fields.Many2one(
        "product.template",
        string="Producto",
        store=True,
        required=False,
        help="Producto/Servicio A Trabajar",
        tracking=True,
        domain="[('type', '=', 'service')]",
    )

    # Metodo para requerimiento a nivel modelo
    @api.constrains("producto")
    def _check_producto_required(self):
        for record in self:
            if not record.producto:
                raise ValidationError(
                    "El campo 'Producto' es obligatorio para los Avances Fisicos."
                )

    especialidad_producto = fields.Many2one(
        string="Especialidad",
        related="producto.categ_id",
        store=True,
        help="Especialidad Del Producto",
        tracking=True,
    )
    unidad_medida = fields.Many2one(
        string="Unidad",
        related="producto.uom_id",
        store=True,
        help="Unidad En La Que Se Mide Producto Ejemplo: Lote, Pza.",
        tracking=True,
    )
    precio_unidad = fields.Float(
        related="producto.list_price",
        string="Precio Unitario",
        store=True,
        help="Precio Unitario Del Producto (Este Precio Es Sin IVA)",
        tracking=True,
    )

    # Datos Generales del Servicio
    oc_pedido = fields.Char(
        string="OC/Pedido",
        related="project_id.name",
        store=True,
        help="Orden De Venta (Este Campo Depende Directamente De Tener Una Orden De Venta)",
        tracking=True,
    )
    date = fields.Date(
        store=True,
        string="Fecha",
        required=True,
        help="Fecha En Que Se Realizo El Trabajo",
        tracking=True,
    )
    ct = fields.Many2one(
        "centro.trabajo.avance",
        string="CT",
        store=True,
        required=True,
        onchange="1",
        help="Centro De Trabajo Donde Se Esta Realizando El Trabajo",
        tracking=True,
    )
    cliente = fields.Many2one(
        "res.partner",
        string="Cliente",
        compute="_compute_cliente",
        store=True,
        tracking=True,
    )

    @api.depends("ct")
    def _compute_cliente(self):
        for record in self:
            if record.ct and record.ct.cliente:
                record.cliente = record.ct.cliente
            else:
                record.cliente = False

    or_rfq = fields.Char(
        string="OR/RFQ",
        store=True,
        help="Cotizaciónes",
        stracking=True,
    )

    especialidad_trabajo = fields.Many2one(
        string="Especialidad De Trabajo",
        related="task_id.disc",
        store=True,
        help="Especialidad Del Trabajo (Este Dependera Directamente De La Etiquetas En La Orden De Venta)",
        tracking=True,
    )  # related='task_id.disc' cambiar despues a tipo char y quitar el related

    no_cotizacion = fields.Char(
        string="No. Cotización",
        store=True,
        tracking=True,
    )

    # Descripción detallada del trabajo
    planta = fields.Many2one(
        "planta.avance",
        string="Planta",
        store=True,
        required=True,
        help="Planta En La Que Se Realizara El Trabajo",
        tracking=True,
    )

    hora_inicio = fields.Float(
        string="Hora De Inicio",
        store=True,
        help="Hora Inicio Del Trabajo",
        required=True,
        tracking=True,
    )

    hora_termino = fields.Float(
        string="Hora De Termino",
        store=True,
        help="Hora Termino Del Trabajo",
        required=True,
        tracking=True,
    )

    responsible_id = fields.Many2one(
        "hr.employee",
        string="Supervisor Interno",
        domain="[('supervisa', '=', True)]",
        required=True,
        help="Supervisor Del Trabajo Interno (AYASA)",
        tracking=True,
    )

    supervisorplanta = fields.Many2one(
        "supervisor.area",
        string="Supervisor Cliente",
        required=True,
        help="Supervisor Del Trabajo Por Parte Del Cliente",
        tracking=True,
    )

    area_id = fields.Many2one(
        "area.avance",
        string="Area",
        store=True,
        required=True,
        help="Area En La Cual Se Realizara El Trabajo",
        tracking=True,
    )

    area = fields.Char(string="Area", store=True)

    licencia = fields.Char(
        string="Licencia/OM",
        store=True,
        size=20,  # 8
        required=True,
        help="Licencia Proporcionado Por El Cliente/Planta Para Poder Realizar El Trabajo",
        tracking=True,
    )

    # Avance Actual
    unit_progress = fields.Float(string="Avance De unidades", default=0.0)
    actual_progress_percentage = fields.Float(
        compute="_actual_progress_percentage", string="Avance Porcentual", default=0.0
    )
    virtual_quant_progress = fields.Float(
        string="Unidades Entregadas (virtual)",
        compute="_virtual_quant_progress",
        default=0.0,
    )
    missing_quant = fields.Float(string="Unidades Faltantes", compute="_missing_quant")

    # Avance del Servicio
    quant_total = fields.Float(related="task_id.total_pieces", default=0.0)
    sale_current = fields.Float(
        string="Avance Del Subtotal", compute="_sale_current", store=True
    )
    virtual_total_progress = fields.Integer(
        string="Progreso Total (virtual)", compute="_virtual_total_progress", default=0
    )

    # Estado de la Facturación
    bitacorapmv = fields.Boolean(
        string="Bitacora PMV",
        default=False,
        help="Indica si este avance cuenta con bitacora",
    )
    om = fields.Char(string="# OM")
    numlic = fields.Char(string="#Bitacora/Lic.", store=True)
    cot = fields.Char(string="#Cot/Presupuesto", store=True)
    estimado = fields.Boolean(
        string="Estimado",
        default=False,
        help="Indica si este avance ya ha sido estimado",
    )
    avanceparc = fields.Char(string="Avance Parcial")
    datefact = fields.Date(string="Fecha De Factura", store=True)
    factura = fields.Many2one(
        "account.move",
        string="Factura",
        domain="[('state', '=', 'posted'), ('move_type', '=', 'out_invoice')]",
    )
    sale_total = fields.Float(
        string="Subtotal De La Venta", compute="_sale_total", store=True
    )
    sale_actual = fields.Float(
        string="Subtotal Entregado", compute="_sale_actual", store=True
    )
    sale_missing = fields.Float(
        string="Subtotal Faltante", compute="_sale_missing", store=True
    )

    proj = fields.Many2one(related="update_id.project_id", store=True)
    projid = fields.Integer(related="proj.id", string="ID Del Proyecto", store=True)
    projname = fields.Char(
        related="proj.name", string="Nombre Del Proyecto", store=True
    )
    prev_progress = fields.Integer(
        related="task_id.progress", string="Current Progress", default=0
    )
    quant_progress = fields.Float(
        string="Unidades Entregadas", compute="_quant_progress", store=True, default=0.0
    )
    actual_progress = fields.Integer(
        compute="_actual_progress", string="Avance", default=0
    )
    total_progress = fields.Integer(
        string="Progreso Total", compute="_total_progress", store=True, default=0
    )
    total_progress_percentage = fields.Float(compute="_total_progress_percentage")

    # Text
    sale_current_text = fields.Char(
        string="Avance Del subtotal (pesos)", compute="_sale_current_text", store=True
    )
    sale_actual_text = fields.Char(
        string="Subtotal Entregado (pesos)", compute="_sale_actual_text", store=True
    )
    sale_total_text = fields.Char(
        string="Subtotal De La Venta (pesos)", compute="_sale_total_text", store=True
    )
    sale_missing_text = fields.Char(
        string="Subtotal Faltante (pesos)", compute="_sale_missing_text", store=True
    )

    task_name = fields.Char(related="task_id.name", string="Nombre De La Tarea")
    domain = fields.Char(string="Dominio", compute="_dom")
    color = fields.Integer(related="update_id.color", string="Color")
    estado = fields.Selection(related="update_id.status", string="Estado Tarea")

    serv_assig = fields.Selection(
        string="Estatus De Servicio",
        selection=[("assig", "Con OS"), ("no_assig", "Sin OS")],
        compute="_compute_serv_assig_computed",
        store=True,  # Asegúrate de que esté almacenado
    )

    cliente_ct = fields.Many2one("res.partner", related="ct.cliente", store=True)

    # Metodos Nuevos
    # Metodo para obtener la fecha del día y agregar el campo Date
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res["date"] = date.today()
        return res

    # Metodo para validación de hora inicio y termino cumplan con el formato de 24hrs
    @api.constrains("hora_inicio", "hora_termino")
    def _check_horas_validas(self):
        for rec in self:
            if rec.hora_inicio < 0.0 or rec.hora_inicio >= 24.0:
                raise ValidationError(
                    "La hora de inicio debe estar entre 00:00 y 23:59."
                )
            if rec.hora_termino < 0.0 or rec.hora_termino >= 24.0:
                raise ValidationError(
                    "La hora de término debe estar entre 00:00 y 23:59."
                )
            if rec.hora_termino <= rec.hora_inicio:
                raise ValidationError(
                    "La hora de término debe ser posterior a la hora de inicio."
                )

    # Metodo para asignar si cuenta con orden de servicio o no
    @api.depends("sale_order_id.serv_assig")
    def _compute_serv_assig_computed(self):
        for record in self:
            record.serv_assig = record.sale_order_id.serv_assig

    # Metodo para validación de Cliente CT corresponda con Cliente Planta, Area, Supervisor Cliente
    planta_domain = fields.Char(compute="_compute_domains", store=True)
    area_domain = fields.Char(compute="_compute_domains", store=True)
    supervisor_domain = fields.Char(compute="_compute_domains", store=True)

    @api.depends("ct.cliente")
    def _compute_domains(self):
        for record in self:
            if record.ct and record.ct.cliente:
                domain = [("cliente", "=", record.ct.cliente.id)]
                domain_str = str(domain)
            else:
                domain_str = str([("id", "=", False)])

            record.planta_domain = domain_str
            record.area_domain = domain_str
            record.supervisor_domain = domain_str

            # Limpieza de campos si no coinciden
            if record.planta and record.planta.cliente != record.ct.cliente:
                record.planta = False
            if record.area_id and record.area_id.cliente != record.ct.cliente:
                record.area_id = False
            if (
                record.supervisorplanta
                and record.supervisorplanta.cliente != record.ct.cliente
            ):
                record.supervisorplanta = False

    @api.constrains("ct", "planta", "area_id", "supervisorplanta")
    def _check_client_consistency(self):
        for record in self:
            main_client = record.ct.cliente
            # Verificación que los campos clientes coinciden con el Cliente CT.
            if record.planta and record.planta.cliente != main_client:
                raise ValidationError(
                    f"El cliente de la planta '{record.planta.name}' no coincide con el cliente del CT '{record.ct.name}'."
                )
            if record.area_id and record.area_id.cliente != main_client:
                raise ValidationError(
                    f"El cliente del área '{record.area_id.name}' no coincide con el cliente del CT '{record.ct.name}'."
                )
            if (
                record.supervisorplanta
                and record.supervisorplanta.cliente != main_client
            ):
                raise ValidationError(
                    f"El cliente del supervisor '{record.supervisorplanta.name}' no coincide con el cliente del CT '{record.ct.name}'."
                )

    invoiced = fields.Float(string="Facturado", related="task_id.invoiced", store=True)
    is_invoiced = fields.Boolean(
        string="Facturado",
        default=False,
        help="Indica si este avance ya ha sido facturado",
    )
    cotizacion = fields.Char(string="# Cotización")

    @api.onchange("factura")
    def _onchange_factura(self):
        if self.factura:
            self.datefact = self.factura.invoice_date

    def action_mark_invoiced(self):
        for record in self:
            record.is_invoiced = True
            record.state = "fact"

    def action_mark_not_invoiced(self):
        for record in self:
            record.is_invoiced = False
            record.state = "no_fact"

    def action_mark_incobrable(self):
        for record in self:
            record.is_invoiced = False
            record.state = "inc"

    @api.depends("unit_progress")
    def _project_id(self):
        for u in self:
            u.project_id = u.env["project.project"].search(
                [("id", "=", u.projid)], limit=1
            )

    @api.model
    def _chosen_tasks(self):
        for u in self:
            tasks = (
                u.env["project.sub.update"]
                .search([("update_id.id", "=", u.update_id.id)])
                .mapped("task_id.id")
            )
            chosen = ""
            for i in tasks:
                chosen = chosen + str(i) + " "
            return chosen.split()

    @api.depends("unit_progress", "task_id")
    def _quant_progress(self):
        for u in self:
            progress = u.task_id.quant_progress
            u.quant_progress = progress

    @api.depends("unit_progress", "task_id")
    def _actual_progress(self):
        for u in self:
            if u.quant_total > 0:
                progress = (u.unit_progress / u.quant_total) * 100
            else:
                progress = 0
            u.actual_progress = int(progress)

    @api.depends("unit_progress", "task_id")
    def _total_progress(self):
        for u in self:
            if u.quant_total > 0:
                progress = (u.virtual_quant_progress / u.quant_total) * 100
            else:
                progress = 0
            u.total_progress = int(progress)

    @api.depends("unit_progress", "task_id")
    def _actual_progress_percentage(self):
        for u in self:
            u.actual_progress_percentage = u.actual_progress / 100

    @api.depends("unit_progress", "task_id")
    def _total_progress_percentage(self):
        for u in self:
            u.total_progress_percentage = u.virtual_total_progress / 100

    @api.depends("unit_progress", "task_id")
    def _virtual_quant_progress(self):
        for u in self:
            if not u.id:
                if not u._origin.id:
                    progress = u.task_id.quant_progress + u.unit_progress
                else:
                    self_total = (
                        u.env["project.sub.update"]
                        .search(
                            [
                                ("project_id.id", "=", u.project_id.id),
                                ("task_id.id", "=", u.task_id.id),
                                ("id", "<", u._origin.id),
                            ]
                        )
                        .mapped("unit_progress")
                    )
                    progress = sum(self_total) + u.unit_progress
            else:
                self_total = (
                    u.env["project.sub.update"]
                    .search(
                        [
                            ("project_id.id", "=", u.project_id.id),
                            ("task_id.id", "=", u.task_id.id),
                            ("id", "<=", u.id),
                        ]
                    )
                    .mapped("unit_progress")
                )
                progress = sum(self_total)
            u.virtual_quant_progress = progress

    @api.depends("unit_progress", "task_id")
    def _virtual_total_progress(self):
        for u in self:
            if u.quant_total > 0:
                progress = (u.virtual_quant_progress / u.quant_total) * 100
            else:
                progress = 0
            u.virtual_total_progress = int(progress)

    @api.depends("unit_progress", "task_id")
    def _missing_quant(self):
        for u in self:
            u.missing_quant = u.task_id.total_pieces - u.virtual_quant_progress

    @api.depends("unit_progress", "task_id")
    def _sale_current(self):
        for u in self:
            u.sale_current = u.unit_progress * u.task_id.price_unit

    @api.depends("unit_progress", "task_id")
    def _sale_actual(self):
        for u in self:
            u.sale_actual = u.virtual_quant_progress * u.task_id.price_unit

    # Campo A Modificar
    @api.depends("unit_progress", "task_id")
    def _sale_total(self):
        for u in self:
            u.sale_total = u.task_id.total_pieces * u.task_id.price_unit

    @api.depends("unit_progress", "task_id")
    def _sale_missing(self):
        for u in self:
            u.sale_missing = u.sale_total - u.sale_actual

    @api.depends("unit_progress", "task_id")
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

    @api.depends("unit_progress", "task_id")
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

    @api.depends("unit_progress", "task_id")
    def _sale_total_text(self):
        for u in self:
            sale = "% .2f" % u.sale_total
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_total_text = "$" + sale

    @api.depends("unit_progress", "task_id")
    def _sale_missing_text(self):
        for u in self:
            sale = "% .2f" % u.sale_missing
            value_len = sale.find(".")
            for i in range(value_len, 0, -1):
                sale = (
                    sale[:i] + "," + sale[i:]
                    if (value_len - i) % 3 == 0 and value_len != i
                    else sale
                )
            u.sale_missing_text = "$" + sale

    @api.onchange("task_id", "unit_progress")
    def _task_domain(self):
        tasks = [0 for c in range(len(self.update_id.sub_update_ids))]
        task_ids = ""
        i = 0
        for u in self.update_id.sub_update_ids:
            tasks[i] = u.task_id.id
            task_ids = task_ids + str(u.task_id.id) + " "
            i = i + 1
        domain = [
            ("project_id.id", "=", self.project_id.id),
            ("is_complete", "=", False),
            ("id", "not in", tasks),
        ]
        return {"domain": {"task_id": domain}}

    @api.depends("task_id")
    def _dom(self):
        tasks = [0 for c in range(len(self.update_id.sub_update_ids))]
        task_ids = ""
        i = 0
        for u in self.update_id.sub_update_ids:
            tasks[i] = u.task_id.id
            task_ids = task_ids + str(u.task_id.id) + " "
            i = i + 1
        domain = str(tasks)
        self.domain = domain

    """
    @api.constrains('task_id')
    def _update_task(self):
        for u in self:
            if not u.task_id:
                raise ValidationError("Tiene que seleccionar una tarea")
    """

    @api.constrains("quant_progress")
    def _update_units(self):
        for u in self:
            if u.task_id:
                if u.quant_progress > u.quant_total:
                    raise ValidationError("Sobrepasa el número de unidades pedidas")

    @api.constrains("unit_progress")
    def _check_units(self):
        for u in self:
            if u.task_id:
                if u.unit_progress <= 0:
                    raise ValidationError("Cantidad inválida de unidades")

    @api.constrains("item_ids")
    def _check_unique_items(self):
        for u in self:
            item_ids = u.item_ids.mapped("item_id")
            if len(item_ids) != len(set(item_ids)):
                raise ValidationError("No se pueden agregar ítems duplicados.")

    @api.constrains("sub_update_ids.task_id")
    def _check_unique_task_id(self):
        for u in self:
            task_ids = u.sub_update_ids.mapped("task_id")
            if len(task_ids) != len(set(task_ids)):
                raise ValidationError("No se pueden agregar tareas duplicadas.")

    @api.model
    def update_sale_totals(self):
        sub_updates = self.search([])
        for sub_update in sub_updates:
            if sub_update.task_id:
                sub_update.sale_total = (
                    sub_update.task_id.total_pieces * sub_update.task_id.price_unit
                )
                sub_update.sale_current = (
                    sub_update.unit_progress * sub_update.task_id.price_unit
                )