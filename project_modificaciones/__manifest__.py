{
    "name": "Modificaciones de Project",
    "version": "17.1",
    "author": "Mauricio and Antonio",
    "depends": ["base", "sale", "hr", "project", "sale_project", "account"],
    "license": "AGPL-3",
    "data": [
        #
        "data/sequences.xml",
        # Archivos de seguridad primero
        "security/project_security.xml",
        "security/ir.model.access.csv",
        "security/ir.model.access.xml",
        # Archivos de vistas y menús después
        "views/analytic_account_views.xml",
        "views/project_sub_update_wizard_views.xml",
        "views/analytic_transfer_wizard_views.xml",
        "views/project_task_extra_views.xml",
        "views/extra_project_update_views.xml",
        "views/project_extra_views.xml",
        "views/sale_order_ex.xml",
        "views/project_tags_views.xml",
        "views/project_sub_update_views.xml",
        "views/supervisor_area_views.xml",
        "views/pending_services.xml",
        "views/pending_service_report.xml",
        "report/report_license_templates.xml",
        "views/menu_actions.xml",  # Este debe ser uno de los últimos
    ],
    "assets": {
        "web.assets_backend": [
            "project_modificaciones/static/src/**/*",
        ],
    },
    "category": "Technical",
    "license": "AGPL-3",
    "installable": True,
    "auto_install": False,
    "application": True,
}
